'''
Module for user and message reports.

New in 0.8.
'''

from flask import Blueprint, redirect, request, render_template, url_for
from .models import Report, REPORT_MEDIA_USER, REPORT_MEDIA_MESSAGE, report_reasons
from .utils import get_current_user
import datetime

bp = Blueprint('reports', __name__, url_prefix='/report')

@bp.route('/user/<int:userid>', methods=['GET', 'POST'])
def report_user(userid):
    if request.method == "POST":
        Report.create(
            media_type=REPORT_MEDIA_USER,
            media_id=userid,
            sender=get_current_user(),
            reason=request.form['reason'],
            created_date=datetime.datetime.now()
        )
        return redirect(url_for('reports.report_done'))
    return render_template('report_user.html', report_reasons=report_reasons)

@bp.route('/message/<int:userid>', methods=['GET', 'POST'])
def report_message(userid):
    if request.method == "POST":
        Report.create(
            media_type=REPORT_MEDIA_MESSAGE,
            media_id=userid,
            sender=get_current_user(),
            reason=request.form['reason'],
            created_date=datetime.datetime.now()
        )
        return redirect(url_for('reports.report_done'))
    return render_template('report_message.html', report_reasons=report_reasons)

@bp.route('/done', methods=['GET', 'POST'])
def report_done():
    return render_template('report_done.html')
