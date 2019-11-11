'''
Management of reports and the entire site.

New in 0.8.
'''

from flask import Blueprint, redirect, render_template, request, url_for
from .models import User, Message, Report, report_reasons, REPORT_STATUS_ACCEPTED, \
    REPORT_MEDIA_USER, REPORT_MEDIA_MESSAGE
from .utils import pwdhash, object_list
from functools import wraps

bp = Blueprint('admin', __name__, url_prefix='/admin')

def check_auth(username, password):
    try:
        return User.get((User.username == username) & (User.password == pwdhash(password))
            ).is_admin
    except User.DoesNotExist:
        return False

def admin_required(f):
    @wraps(f)
    def wrapped_view(**kwargs):
        auth = request.authorization
        if not (auth and check_auth(auth.username, auth.password)):
            return ('Unauthorized', 401, {
                'WWW-Authenticate': 'Basic realm="Login Required"'
            })
        return f(**kwargs)
    return wrapped_view

def review_reports(status, media_type, media_id):
    (Report
     .update(status=status)
     .where((Report.media_type == media_type) & (Report.media_id == media_id))
     .execute())
    if status == REPORT_STATUS_ACCEPTED:
        if media_type == REPORT_MEDIA_USER:
            user = User[media_id]
            user.is_disabled = 2
            user.save()
        elif media_type == REPORT_MEDIA_MESSAGE:
            Message.delete().where(Message.id == media_id).execute()

@bp.route('/')
@admin_required
def homepage():
    return render_template('admin_home.html')

@bp.route('/reports')
@admin_required
def reports():
    return object_list('admin_reports.html', Report.select().order_by(Report.created_date.desc()), 'report_list', report_reasons=dict(report_reasons))

@bp.route('/reports/<int:id>', methods=['GET', 'POST'])
@admin_required
def reports_detail(id):
    report = Report[id]
    if request.method == 'POST':
        if request.form.get('take_down'):
            review_reports(REPORT_STATUS_ACCEPTED, report.media_type, report.media_id)
        elif request.form.get('discard'):
            review_reports(REPORT_STATUS_DECLINED, report.media_type, report.media_id)
        return redirect(url_for('admin.reports'))
    return render_template('admin_report_detail.html', report=report, report_reasons=dict(report_reasons))
