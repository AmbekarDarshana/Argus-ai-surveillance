# routes/dashboard.py

from flask import Blueprint, render_template, current_app, redirect, url_for, session, request, flash
from models.video import get_all_videos, get_video_by_id
from datetime import datetime
from collections import defaultdict

bp = Blueprint('main', __name__)


@bp.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('auth.login'))

    user = session.get('user', {})
    role = session.get('role')
    user_id = user.get('_id')
    db = current_app.db

    # ========== GET VIDEOS ==========
    # Admin sees all videos
    # Client sees only videos assigned to them OR from their cameras
    if role == 'admin':
        videos = list(db.videos.find({}))
    else:
        # Get client's assigned cameras first
        client_cameras = list(db.cameras.find({'owner_id': user_id}))
        camera_ids = [str(c['_id']) for c in client_cameras]
        camera_names = [c.get('name', c.get('location', '')) for c in client_cameras]

        # Get videos that belong to this client OR linked to their cameras
        videos = list(db.videos.find({
            '$or': [
                {'owner_id': user_id},
                {'camera_id': {'$in': camera_ids}}
            ]
        }))

    # Convert _id to string
    for v in videos:
        v['_id'] = str(v['_id'])

    video_map = {v['_id']: v.get('location', 'Camera') for v in videos}

    # ========== GET CAMERAS FOR CLIENT ==========
    # Client also sees their assigned cameras (even without videos)
    assigned_cameras = []
    if role != 'admin':
        assigned_cameras = list(db.cameras.find({'owner_id': user_id}))
        for c in assigned_cameras:
            c['_id'] = str(c['_id'])

    # ========== SELECTED VIDEO ==========
    selected_video_id = request.args.get('video_id')
    current_video = None
    video_url = None

    if selected_video_id:
        current_video = get_video_by_id(db, selected_video_id)
        if current_video:
            # Security: client can only view their own videos
            if role != 'admin' and current_video.get('owner_id') != user_id:
                current_video = None
            else:
                video_url = url_for('video.stream_video', video_id=selected_video_id)

    # ========== ANOMALIES ==========
    query = {'$or': [{'is_live': {'$exists': False}}, {'is_live': False}]}

    if selected_video_id:
        query['video_id'] = selected_video_id
    elif role != 'admin':
        # Client only sees their own anomalies
        video_ids = [v['_id'] for v in videos]
        if video_ids:
            query['video_id'] = {'$in': video_ids}
        else:
            query['video_id'] = 'none'  # No videos = no anomalies

    filter_type = request.args.get('type')
    if filter_type:
        query['anomaly_type'] = filter_type

    anomalies = list(db.anomalies.find(query).sort('frame_timestamp', -1))
    for a in anomalies:
        a['_id'] = str(a['_id'])
        if 'video_id' in a:
            a['video_id'] = str(a['video_id'])

    # ========== CHART DATA ==========
    daily_counts = defaultdict(int)
    for a in anomalies:
        ts = a.get('timestamp') or a.get('created_at') or a.get('detection_time')
        if ts:
            if isinstance(ts, str):
                date_key = ts.split('T')[0]
            else:
                date_key = ts.strftime('%Y-%m-%d')
            daily_counts[date_key] += 1

    chart_data = [{'day': k, 'count': v} for k, v in daily_counts.items()]

    summary = {
        'today': len(anomalies),
        'week': len(anomalies),
        'cameras': len(videos) + len(assigned_cameras)
    }

    return render_template(
        'dashboard.html',
        videos=videos,
        video=current_video,
        video_url=video_url,
        anomalies=anomalies,
        video_map=video_map,
        assigned_cameras=assigned_cameras,
        summary=summary,
        chart_data=chart_data,
        filters={'type': filter_type},
        role=role,
        user=user
    )


@bp.route('/subscription')
def subscription():
    if 'user' not in session:
        return redirect(url_for('auth.login'))
    return render_template('subscription.html', user=session.get('user'))


@bp.route('/support', methods=['GET', 'POST'])
def support():
    if 'user' not in session:
        return redirect(url_for('auth.login'))

    db = current_app.db
# routes/dashboard.py

from flask import Blueprint, render_template, current_app, redirect, url_for, session, request, flash
from models.video import get_video_by_id
from datetime import datetime, timedelta
from collections import defaultdict

bp = Blueprint('main', __name__)


def _as_str(value):
    return str(value) if value is not None else None


@bp.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('auth.login'))

    user = session.get('user', {})
    role = session.get('role', 'user')
    user_id = _as_str(user.get('_id'))
    db = current_app.db

    # =========================================
    # 1) CAMERAS
    # Admin: all cameras
    # Client: only owned cameras
    # =========================================
    if role == 'admin':
        assigned_cameras = list(db.cameras.find({}))
    else:
        assigned_cameras = list(db.cameras.find({'owner_id': user_id}))

    for c in assigned_cameras:
        c['_id'] = _as_str(c.get('_id'))
        c['owner_id'] = _as_str(c.get('owner_id'))

    camera_ids = [c['_id'] for c in assigned_cameras]

    # =========================================
    # 2) VIDEOS
    # Admin: all videos
    # Client: own videos + videos linked to own cameras
    # Exclude pure demo noise unless owned by user
    # =========================================
    if role == 'admin':
        videos = list(db.videos.find({}))
    else:
        videos = list(db.videos.find({
            '$or': [
                {'owner_id': user_id},
                {'camera_id': {'$in': camera_ids}},
            ]
        }))

    for v in videos:
        v['_id'] = _as_str(v.get('_id'))
        v['owner_id'] = _as_str(v.get('owner_id'))
        if v.get('camera_id') is not None:
            v['camera_id'] = _as_str(v.get('camera_id'))

    video_ids = [v['_id'] for v in videos]

    # Map IDs to readable names for the anomaly log
    video_map = {}
    for v in videos:
        video_map[v['_id']] = v.get('location') or v.get('name') or 'Video'
    for c in assigned_cameras:
        video_map[c['_id']] = c.get('name') or c.get('location') or 'Live Camera'

    # =========================================
    # 3) SELECTED VIDEO (with security)
    # =========================================
    selected_video_id = request.args.get('video_id')
    current_video = None
    video_url = None

    if selected_video_id:
        current_video = get_video_by_id(db, selected_video_id)
        if current_video:
            current_video['_id'] = _as_str(current_video.get('_id'))
            current_video['owner_id'] = _as_str(current_video.get('owner_id'))

            # Client can open only own video
            if role != 'admin' and current_video.get('owner_id') != user_id:
                flash('Not authorized to view this video.', 'danger')
                current_video = None
                selected_video_id = None
            else:
                video_url = url_for('video.stream_video', video_id=selected_video_id)

    # =========================================
    # 4) ANOMALIES (THIS WAS THE MAIN BUG)
    # Must include:
    # - owner_id match
    # - video_id match
    # - camera_id match
    # so live + uploaded both show correctly
    # =========================================
    query = {}

    if selected_video_id and current_video:
        # Drill-down into one video
        query['video_id'] = selected_video_id
    else:
        if role == 'admin':
            # Admin sees all anomalies
            query = {}
        else:
            # Client scope
            or_clauses = [{'owner_id': user_id}]
            if video_ids:
                or_clauses.append({'video_id': {'$in': video_ids}})
            if camera_ids:
                or_clauses.append({'camera_id': {'$in': camera_ids}})
            query['$or'] = or_clauses

    # Optional type filter from UI
    filter_type = request.args.get('type')
    if filter_type:
        query['anomaly_type'] = filter_type

    anomalies = list(
        db.anomalies.find(query).sort([
            ('detection_time', -1),
            ('created_at', -1),
            ('frame_timestamp', -1)
        ]).limit(300)
    )

    for a in anomalies:
        a['_id'] = _as_str(a.get('_id'))
        a['video_id'] = _as_str(a.get('video_id'))
        a['camera_id'] = _as_str(a.get('camera_id'))
        a['owner_id'] = _as_str(a.get('owner_id'))

        # Ensure score exists for template checks
        if a.get('anomaly_score') is None:
            a['anomaly_score'] = 0

    # =========================================
    # 5) CHART + SUMMARY (real today/week)
    # =========================================
    now = datetime.now()
    today_key = now.strftime('%Y-%m-%d')
    week_cutoff = now - timedelta(days=7)

    daily_counts = defaultdict(int)
    today_count = 0
    week_count = 0

    for a in anomalies:
        ts = a.get('detection_time') or a.get('created_at') or a.get('timestamp')
        ts_dt = None
        day = None

        if isinstance(ts, datetime):
            ts_dt = ts
            day = ts.strftime('%Y-%m-%d')
        elif isinstance(ts, str) and ts:
            day = ts.split('T')[0]
            try:
                ts_dt = datetime.fromisoformat(ts.replace('Z', ''))
            except Exception:
                ts_dt = None

        if day:
            daily_counts[day] += 1
            if day == today_key:
                today_count += 1

        if ts_dt and ts_dt >= week_cutoff:
            week_count += 1

    chart_data = [
        {'day': day, 'count': daily_counts[day]}
        for day in sorted(daily_counts.keys())
    ]

    summary = {
        'today': today_count,
        'week': week_count,
        'cameras': len(assigned_cameras) if role != 'admin' else len(assigned_cameras),
    }

    return render_template(
        'dashboard.html',
        videos=videos,
        video=current_video,
        video_url=video_url,
        anomalies=anomalies,
        video_map=video_map,
        assigned_cameras=assigned_cameras,
        summary=summary,
        chart_data=chart_data,
        filters={'type': filter_type or ''},
        role=role,
        user=user
    )


@bp.route('/subscription')
def subscription():
    if 'user' not in session:
        return redirect(url_for('auth.login'))
    return render_template('subscription.html', user=session.get('user'))


@bp.route('/support', methods=['GET', 'POST'])
def support():
    if 'user' not in session:
        return redirect(url_for('auth.login'))

    db = current_app.db
    user_id = _as_str(session['user']['_id'])

    if request.method == 'POST':
        ticket = {
            'user_id': user_id,
            'user_email': session['user'].get('email'),
            'user_name': session['user'].get('name'),
            'subject': request.form.get('subject'),
            'message': request.form.get('message'),
            'status': 'open',
            'created_at': datetime.now()
        }
        # Keep one collection name everywhere
        db.tickets.insert_one(ticket)
        flash('Ticket submitted!', 'success')
        return redirect(url_for('main.support'))

    my_tickets = list(db.tickets.find({'user_id': user_id}).sort('created_at', -1))
    for t in my_tickets:
        t['_id'] = _as_str(t.get('_id'))

    return render_template('support.html', tickets=my_tickets, user=session.get('user'))
    if request.method == 'POST':
        subject = request.form.get('subject')
        message = request.form.get('message')
        ticket = {
            'user_id': session['user']['_id'],
            'user_email': session['user']['email'],
            'subject': subject,
            'message': message,
            'status': 'open',
            'created_at': datetime.now()
        }
        db.support.insert_one(ticket)
        flash('Ticket submitted!', 'success')
        return redirect(url_for('main.support'))

    my_tickets = list(db.support.find({'user_id': session['user']['_id']}).sort('created_at', -1))
    return render_template('support.html', tickets=my_tickets, user=session.get('user'))