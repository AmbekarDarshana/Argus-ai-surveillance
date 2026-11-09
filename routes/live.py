# routes/live.py
"""
Live Camera Demo & Recording Lab
Developer / Sandbox environment for testing detection, recording, FFmpeg, and AI analysis.
"""
from flask import Blueprint, render_template, request, jsonify, Response, current_app, session, redirect, url_for
import cv2
import time
import threading
import os
import shutil
import subprocess
from datetime import datetime
from anomaly_engine.detector import get_detector, process_video
from config import Config
from bson import ObjectId
from models.video import create_video, get_video_by_id
from models.recording import (
    start_recording, stop_recording, update_recording_frame_count,
    add_anomaly_to_recording, mark_recording_error, get_all_recordings
)

live_bp = Blueprint('live', __name__, url_prefix='/live')


# ===================== FFMPEG CONVERTER =====================

def get_ffmpeg_path():
    try:
        import imageio_ffmpeg
        path = imageio_ffmpeg.get_ffmpeg_exe()
        if os.path.exists(path):
            return path
    except ImportError:
        pass

    import shutil as sh
    system_ffmpeg = sh.which('ffmpeg')
    if system_ffmpeg:
        return system_ffmpeg

    return None


def convert_to_browser_format(input_path):
    ffmpeg_path = get_ffmpeg_path()
    if ffmpeg_path is None:
        print("[CONVERT] FFmpeg not found!")
        return False

    output_path = input_path + '.tmp_web.mp4'

    try:
        cmd = [
            ffmpeg_path, '-y',
            '-i', input_path,
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-crf', '23',
            '-c:a', 'aac',
            '-movflags', '+faststart',
            output_path
        ]
        result = subprocess.run(cmd, check=True, capture_output=True, timeout=300)

        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            os.remove(input_path)
            os.rename(output_path, input_path)
            return True
        return False

    except Exception as e:
        print(f"[CONVERT] Error: {e}")
        if os.path.exists(output_path):
            os.remove(output_path)
        return False


# ===================== GLOBAL CAMERA STATE =====================

camera_state = {
    'cap': None,
    'is_running': False,
    'active_user_id': None,  # Locks the hardware webcam to one user at a time
    'lock': threading.Lock(),
    'latest_detections': [],
    'latest_anomalies': [],
    'is_recording': False,
    'video_writer': None,
    'recording_id': None,
    'recording_filename': None,
    'recording_frame_count': 0,
    'recording_lock': threading.Lock(),
}


# ===================== VIDEO STREAMING GENERATOR =====================

def generate_frames(user_id):
    """Video streaming generator function with Behavior Detection + Recording."""
    global camera_state
    yolo, classifier = get_detector()
    frame_counter = 0
    prev_detections = []
    alert_cooldowns = {}
    last_db_update = time.time()

    while camera_state['is_running'] and camera_state['cap']:
        success, frame = camera_state['cap'].read()
        if not success:
            break

        frame = cv2.resize(frame, (640, 480))
        frame_counter += 1
        current_time = time.time()

        with camera_state['recording_lock']:
            if camera_state['is_recording'] and camera_state['video_writer'] is not None:
                try:
                    camera_state['video_writer'].write(frame)
                    camera_state['recording_frame_count'] += 1

                    if (current_time - last_db_update) > 5.0:
                        db = current_app.db
                        update_recording_frame_count(db, camera_state['recording_id'], camera_state['recording_frame_count'])
                        last_db_update = current_time
                except Exception as e:
                    print(f"Video write error: {e}")

        if frame_counter % 3 == 0:
            try:
                raw_detections = yolo.detect(frame)
                detections = [d for d in raw_detections if d.confidence > 0.40]
                anomalies = classifier.classify(detections, current_time, prev_detections)
                valid_anomalies = []

                for anomaly in anomalies:
                    if anomaly.score < 0.60:
                        continue
                    last_alert = alert_cooldowns.get(anomaly.type, 0)
                    if (current_time - last_alert) < 5.0:
                        continue
                    alert_cooldowns[anomaly.type] = current_time

                    try:
                        db = current_app.db
                        log_data = {
                            "video_id": "demo_webcam_01",
                            "owner_id": user_id,  # <--- CRITICAL FIX: Link anomaly to current user
                            "anomaly_type": anomaly.type,
                            "anomaly_score": round(anomaly.score, 2),
                            "frame_timestamp": current_time,
                            "description": f"Demo Lab: {anomaly.description}",
                            "objects_detected": anomaly.objects,
                            "detection_count": len(detections),
                            "created_at": datetime.now(),
                            "is_live": True,
                            "source": "demo_lab"
                        }
                        result = db.anomalies.insert_one(log_data)

                        with camera_state['recording_lock']:
                            if camera_state['is_recording'] and camera_state['recording_id']:
                                add_anomaly_to_recording(db, camera_state['recording_id'], result.inserted_id)

                    except Exception as e:
                        print(f"DB Error: {e}")

                    valid_anomalies.append(anomaly)

                camera_state['latest_detections'] = detections
                camera_state['latest_anomalies'] = valid_anomalies
                prev_detections = detections

            except Exception as e:
                print(f"AI Error: {e}")

        # --- DRAWING ---
        annotated = frame.copy()
        for d in camera_state['latest_detections']:
            x, y, w, h = d.bbox
            color = (0, 0, 255) if any(d.label in anom.objects for anom in camera_state['latest_anomalies']) else (0, 255, 0)
            cv2.rectangle(annotated, (x, y), (x + w, y + h), color, 2)
            cv2.putText(annotated, f"{d.label}", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        for i, anomaly in enumerate(camera_state['latest_anomalies']):
            cv2.rectangle(annotated, (5, 5 + (i * 35)), (350, 35 + (i * 35)), (0, 0, 255), -1)
            cv2.putText(annotated, f"ALERT: {anomaly.type.upper()}", (10, 28 + (i * 35)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        with camera_state['recording_lock']:
            if camera_state['is_recording']:
                if int(current_time * 2) % 2 == 0:
                    cv2.circle(annotated, (620, 20), 8, (0, 0, 255), -1)
                cv2.putText(annotated, "REC", (590, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                cv2.putText(annotated, f"Frames: {camera_state['recording_frame_count']}", (10, 470), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

        ret, buffer = cv2.imencode('.jpg', annotated)
        yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')


# ===================== PAGE ROUTES =====================

@live_bp.route('/dashboard', methods=['GET'])
def live_dashboard():
    if 'user' not in session:
        return redirect(url_for('auth.login'))

    dummy_camera = {'_id': 'demo_webcam_01', 'name': 'Demo Lab Webcam', 'location': 'Local System'}
    recordings = []
    try:
        db = current_app.db
        # Filter recordings to only show ones made by this user or the system
        recordings = list(db.recordings.find({
            'camera_id': 'demo_webcam_01',
            '$or': [{'started_by': session['user']['email']}, {'started_by': 'system'}]
        }).sort('start_time', -1).limit(10))
        for r in recordings:
            r['_id'] = str(r['_id'])
    except Exception as e:
        print(f"Error fetching recordings: {e}")

    return render_template('live_cameras.html', camera=dummy_camera, recordings=recordings, is_recording=camera_state['is_recording'])


@live_bp.route('/video_feed')
def video_feed():
    if 'user' not in session:
        return "Unauthorized", 401
    user_id = str(session['user']['_id'])
    return Response(generate_frames(user_id), mimetype='multipart/x-mixed-replace; boundary=frame')


# ===================== CAMERA CONTROL API =====================

@live_bp.route('/api/start', methods=['POST'])
def api_start_camera():
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    global camera_state
    user_id = str(session['user']['_id'])

    with camera_state['lock']:
        if camera_state['is_running']:
            if camera_state['active_user_id'] != user_id:
                return jsonify({'error': 'Webcam is currently in use by another user.'}), 403
            return jsonify({'status': 'already_started'})

        camera_state['cap'] = cv2.VideoCapture(0)
        camera_state['is_running'] = True
        camera_state['active_user_id'] = user_id

    return jsonify({'status': 'started'})


@live_bp.route('/api/stop', methods=['POST'])
def api_stop_camera():
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    global camera_state
    user_id = str(session['user']['_id'])

    with camera_state['lock']:
        if camera_state['active_user_id'] and camera_state['active_user_id'] != user_id:
            return jsonify({'error': 'Cannot stop a stream started by another user.'}), 403

        with camera_state['recording_lock']:
            if camera_state['is_recording']:
                _stop_recording_internal()

        camera_state['is_running'] = False
        camera_state['active_user_id'] = None
        if camera_state['cap']:
            camera_state['cap'].release()
            camera_state['cap'] = None

    return jsonify({'status': 'stopped'})


# ===================== RECORDING API =====================

@live_bp.route('/api/record/start', methods=['POST'])
def api_start_recording():
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    global camera_state
    user_id = str(session['user']['_id'])

    if not camera_state['is_running'] or camera_state['active_user_id'] != user_id:
        return jsonify({'error': 'Start camera first or camera in use by another.'}), 400

    with camera_state['recording_lock']:
        if camera_state['is_recording']:
            return jsonify({'error': 'Already recording'}), 400

        try:
            os.makedirs(Config.RECORDING_FOLDER, exist_ok=True)
            filename = f"live_recording_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
            filepath = os.path.join(Config.RECORDING_FOLDER, filename)

            writer = cv2.VideoWriter(filepath, cv2.VideoWriter_fourcc(*'mp4v'), 20.0, (640, 480))
            if not writer.isOpened():
                return jsonify({'error': 'Failed to initialize video writer'}), 500

            db = current_app.db
            recording_doc = start_recording(db, {
                'camera_id': 'demo_webcam_01',
                'filename': filepath,
                'resolution': {'width': 640, 'height': 480},
                'fps': 20.0,
                'started_by': session['user'].get('email', 'system')
            })

            camera_state['is_recording'] = True
            camera_state['video_writer'] = writer
            camera_state['recording_id'] = recording_doc['_id']
            camera_state['recording_filename'] = filepath
            camera_state['recording_frame_count'] = 0

            return jsonify({'status': 'recording_started', 'recording_id': recording_doc['_id'], 'filename': filename})
        except Exception as e:
            return jsonify({'error': str(e)}), 500


@live_bp.route('/api/record/stop', methods=['POST'])
def api_stop_recording():
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    global camera_state
    if camera_state['active_user_id'] != str(session['user']['_id']):
        return jsonify({'error': 'Permission denied'}), 403

    with camera_state['recording_lock']:
        if not camera_state['is_recording']:
            return jsonify({'error': 'Not currently recording'}), 400
        result = _stop_recording_internal()

    return jsonify(result)


def _stop_recording_internal():
    global camera_state
    try:
        if camera_state['video_writer']:
            camera_state['video_writer'].release()
            camera_state['video_writer'] = None

        if camera_state['recording_filename'] and os.path.exists(camera_state['recording_filename']):
            convert_to_browser_format(camera_state['recording_filename'])

        db = current_app.db
        stop_recording(db, camera_state['recording_id'], camera_state['recording_frame_count'], camera_state['recording_filename'])

        result = {
            'status': 'recording_stopped',
            'recording_id': camera_state['recording_id'],
            'total_frames': camera_state['recording_frame_count'],
            'filename': camera_state['recording_filename']
        }

        camera_state['is_recording'] = False
        camera_state['recording_id'] = None
        camera_state['recording_filename'] = None
        camera_state['recording_frame_count'] = 0
        return result
    except Exception as e:
        camera_state['is_recording'] = False
        return {'error': str(e)}


# ===================== UPLOAD & ANALYZE =====================

@live_bp.route('/api/record/upload_and_process', methods=['POST'])
def upload_and_process_recording():
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    try:
        data = request.get_json(silent=True) or {}
        recording_id = data.get('recording_id')
        if not recording_id:
            return jsonify({'error': 'No recording_id provided'}), 400

        db = current_app.db
        recording = db.recordings.find_one({'_id': ObjectId(recording_id)})
        if not recording:
            return jsonify({'error': 'Recording not found'}), 404

        source_file = recording.get('filename')
        if not source_file or not os.path.exists(source_file):
            return jsonify({'error': 'File not found on disk'}), 404

        upload_dir = os.path.join(current_app.root_path, 'uploads')
        os.makedirs(upload_dir, exist_ok=True)
        dest_path = os.path.join(upload_dir, os.path.basename(source_file))

        if not os.path.exists(dest_path):
            shutil.copy2(source_file, dest_path)

        user = session['user']
        video_data = {
            'file_path': 'uploads/' + os.path.basename(source_file),
            'location': f"Demo Lab Record {datetime.now().strftime('%m-%d %H:%M')}",
            'resolution': "640x480",
            'status': 'processing',
            'owner_id': user['_id'],
            'source': 'demo_lab',
            'recording_id': recording_id,
            'created_at': datetime.now()
        }

        video_id = str(db.videos.insert_one(video_data).inserted_id)
        db.recordings.update_one({'_id': ObjectId(recording_id)}, {'$set': {'video_id': video_id}})

        anomalies = process_video(db, dest_path, video_id=video_id)
        db.videos.update_one({'_id': ObjectId(video_id)}, {'$set': {'status': 'processed', 'anomaly_count': len(anomalies)}})

        return jsonify({
            'status': 'completed',
            'video_id': video_id,
            'anomalies_found': len(anomalies),
            'dashboard_url': f'/dashboard?video_id={video_id}'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500