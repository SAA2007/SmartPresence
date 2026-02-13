from flask import Blueprint, render_template, Response, session, redirect, url_for, request
from functools import wraps
from web_app.video_stream import video_stream

views_bp = Blueprint('views', __name__)


# ── Auth Decorators ──

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('views.login'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('views.login'))
        if session.get('role') != 'admin':
            return render_template('403.html'), 403
        return f(*args, **kwargs)
    return decorated


# ── Public Routes ──

@views_bp.route('/login')
def login():
    if 'user_id' in session:
        return redirect(url_for('views.dashboard'))
    return render_template('login.html')


@views_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('views.login'))


@views_bp.route('/lookup')
def student_lookup():
    return render_template('lookup.html')


# ── Protected Routes ──

@views_bp.route('/')
@login_required
def dashboard():
    return render_template('dashboard.html')


@views_bp.route('/live')
@login_required
def live():
    return render_template('live.html')


@views_bp.route('/students')
@login_required
def students():
    return render_template('students.html')


@views_bp.route('/enroll')
@login_required
def enroll():
    return render_template('enroll.html')


@views_bp.route('/settings')
@login_required
def settings():
    return render_template('settings.html')


@views_bp.route('/report')
@login_required
def report():
    return render_template('report.html')


@views_bp.route('/timetable')
@login_required
def timetable():
    return render_template('timetable.html')


@views_bp.route('/student/<int:student_id>')
@login_required
def student_detail(student_id):
    return render_template('student_detail.html', student_id=student_id)


# ── Admin-Only Routes ──

@views_bp.route('/users')
@admin_required
def user_management():
    return render_template('user_management.html')


@views_bp.route('/debug')
@admin_required
def debug_page():
    return render_template('debug.html')


# ── Video Feed (requires login) ──

@views_bp.route('/video_feed')
@login_required
def video_feed():
    return Response(video_stream.generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')
