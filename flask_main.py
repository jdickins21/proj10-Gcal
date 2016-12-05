import flask
from flask import render_template
from flask import request
from flask import url_for
import uuid

import json
import logging

# Date handling 
import arrow # Replacement for datetime, based on moment.js
import datetime # But we still need time
from dateutil import tz  # For interpreting local times


# OAuth2  - Google library implementation for convenience
from oauth2client import client
import httplib2   # used in oauth2 flow

# Google API for services 
from apiclient import discovery

###
# Globals
###
import CONFIG

from agenda import *

# Mongo database
from bson.objectid import ObjectId

app = flask.Flask(__name__)
app.debug=CONFIG.DEBUG
app.logger.setLevel(logging.DEBUG)
app.secret_key=CONFIG.secret_key

# Mongo database
from pymongo import MongoClient
import secrets.admin_secrets
import secrets.client_secrets

MONGO_CLIENT_URL = "mongodb://{}:{}@localhost:{}/{}".format(
    secrets.client_secrets.db_user,
    secrets.client_secrets.db_user_pw,
    secrets.admin_secrets.port, 
    secrets.client_secrets.db)

SCOPES = 'https://www.googleapis.com/auth/calendar.readonly'
CLIENT_SECRET_FILE = secrets.admin_secrets.google_key_file  ## You'll need this
APPLICATION_NAME = 'Final class project'

#############################
#
#  Pages (routed from URLs)
#
#############################

@app.route("/")
@app.route("/index")
def index():
  app.logger.debug("Entering index")
  if 'begin_date' not in flask.session:
    init_session_values()
  return render_template('index.html')

@app.route("/participant/<proposal_id>")
def participant(proposal_id):
  flask.session['proposal_id'] = proposal_id
  flask.session['is_participant'] = "True"
  for record in collection.find( { "type": "proposal", "_id": flask.session['proposal_id'] } ):
      flask.session['begin_date'] = record['start_date']
      flask.session['end_date'] = record['end_date']
      flask.session['begin_time'] = record['start_time']
      flask.session['end_time'] = record['end_time']
  return render_template('participant.html')

@app.route("/choose")
def choose():
  ## We'll need authorization to list calendars 
  ## I wanted to put what follows into a function, but had
  ## to pull it back here because the redirect has to be a
  ## 'return' 
  app.logger.debug("Checking credentials for Google calendar access")
  credentials = valid_credentials()
  if not credentials:
    app.logger.debug("Redirecting to authorization")
    return flask.redirect(flask.url_for('oauth2callback'))

  gcal_service = get_gcal_service(credentials)
  app.logger.debug("Returned from get_gcal_service")
  flask.session["calendars"] = list_calendars(gcal_service)
  
  if flask.session['is_participant'] == "True":
      return render_template('participant.html')
  else:
      return render_template('index.html')

def valid_credentials():
    """
    Returns OAuth2 credentials if we have valid
    credentials in the session.  This is a 'truthy' value.
    Return None if we don't have credentials, or if they
    have expired or are otherwise invalid.  This is a 'falsy' value. 
    """
    if 'credentials' not in flask.session:
      return None

    credentials = client.OAuth2Credentials.from_json(
        flask.session['credentials'])

    if (credentials.invalid or
        credentials.access_token_expired):
      return None
    return credentials


def get_gcal_service(credentials):
  """
  We need a Google calendar 'service' object to obtain
  list of calendars, busy times, etc.  This requires
  authorization. If authorization is already in effect,
  we'll just return with the authorization. Otherwise,
  control flow will be interrupted by authorization, and we'll
  end up redirected back to /choose *without a service object*.
  Then the second call will succeed without additional authorization.
  """
  app.logger.debug("Entering get_gcal_service")
  http_auth = credentials.authorize(httplib2.Http())
  service = discovery.build('calendar', 'v3', http=http_auth)
  app.logger.debug("Returning service")
  return service

@app.route('/oauth2callback')
def oauth2callback():
  """
  The 'flow' has this one place to call back to.  We'll enter here
  more than once as steps in the flow are completed, and need to keep
  track of how far we've gotten. The first time we'll do the first
  step, the second time we'll skip the first step and do the second,
  and so on.
  """
  app.logger.debug("Entering oauth2callback")
  flow =  client.flow_from_clientsecrets(
      CLIENT_SECRET_FILE,
      scope= SCOPES,
      redirect_uri=flask.url_for('oauth2callback', _external=True))
  ## Note we are *not* redirecting above.  We are noting *where*
  ## we will redirect to, which is this function. 

  ## The *second* time we enter here, it's a callback 
  ## with 'code' set in the URL parameter.  If we don't
  ## see that, it must be the first time through, so we
  ## need to do step 1. 
  app.logger.debug("Got flow")
  if 'code' not in flask.request.args:
    app.logger.debug("Code not in flask.request.args")
    auth_uri = flow.step1_get_authorize_url()
    return flask.redirect(auth_uri)
    ## This will redirect back here, but the second time through
    ## we'll have the 'code' parameter set
  else:
    ## It's the second time through ... we can tell because
    ## we got the 'code' argument in the URL.
    app.logger.debug("Code was in flask.request.args")
    auth_code = flask.request.args.get('code')
    credentials = flow.step2_exchange(auth_code)
    flask.session['credentials'] = credentials.to_json()
    ## Now I can build the service and execute the query,
    ## but for the moment I'll just log it and go back to
    ## the main screen
    app.logger.debug("Got credentials")
    return flask.redirect(flask.url_for('choose'))

@app.route('/set_partic_name', methods=['POST'])
def set_partic_name():
  """
  The participant has entered in his/her name. We save this
  name in the session object, for later.
  """
  name = request.form.get('name')
  flask.session['name'] = name
  return flask.redirect(flask.url_for("choose"))

@app.route('/setrange', methods=['POST'])
def setrange():
    """
    User chose a date range with the bootstrap daterange
    widget.
    """
    app.logger.debug("Entering setrange")  
    flask.flash("Setrange gave us '{}'".format(
      request.form.get('daterange')))

    daterange = request.form.get('daterange')
    starttime = request.form.get('starttime')
    endtime = request.form.get('endtime')
    name = request.form.get('name')

    flask.session['name'] = name
    flask.session['daterange'] = daterange
    flask.session['text_beg_time'] = starttime
    flask.session['text_end_time'] = endtime
    
    daterange_parts = daterange.split()
    flask.session['begin_date'] = interpret_date(daterange_parts[0])
    flask.session['end_date'] = interpret_date(daterange_parts[2])
    flask.session['begin_time'] = interpret_time(starttime)
    flask.session['end_time'] = interpret_time(endtime)

    flask.session['is_participant'] = "False"

    app.logger.debug("Setrange parsed {} - {}  dates as {} - {}".format(
      daterange_parts[0], daterange_parts[1], 
      flask.session['begin_date'], flask.session['end_date']))

    return flask.redirect(flask.url_for("choose"))

@app.route('/eliminate_candidate')  
def eliminate_candidate():
  """
  The user has checked the "available" times in which he can meet 
  and has pressed "submit". We obtain a revised free list by going 
  through the current free_list and only keeping the available times
  which the user has checked. 
  """
  selected_candidates = request.args.getlist("selected[]")
  flask.session['selected_candidates'] = selected_candidates
  delete_candidate() #now we have revised_free
  if flask.session['is_participant'] == "True":
      store_participant()
  else:
      store_proposer()     
  return "nothing"

@app.route('/participant_finish')
def participant_finish():
  flask.session['display_revised_free'] = create_display_aptlist(flask.session['revised_free'])
  return render_template('participant.html')

@app.route('/proposer_finish')
def proposer_finish():
  #give free list to be displayed 
  #now render index.html cuz now have revised_free and proposal_id
  flask.session['display_revised_free'] = create_display_aptlist(flask.session['revised_free'])
  url = "localhost:5000/participant/" + flask.session['proposal_id']
  flask.session['participant_url'] = url
  return render_template('index.html')

@app.route('/status')
def status():
    """
    Take the intersected free times
    amongst all the people who have currently responded, and the names of all the 
    people who have currently responded from the database. Finally we render
    template status.html.
    """
    create_display_meetinginfo()
    create_display_intersected_times()
    create_display_responders()
    return render_template('status.html')

@app.route('/back_to_partic')
def back_to_partic():
    """
    We redirect the user back to participant.html. 
    """
    return render_template('participant.html')

####
#
#   Initialize session variables 
#
####

def init_session_values():
    """
    Start with some reasonable defaults for date and time ranges.
    Note this must be run in app context ... can't call from main. 
    """
    # Default date span = tomorrow to 1 week from now
    now = arrow.now('local')     # We really should be using tz from browser
    tomorrow = now.replace(days=+1)
    nextweek = now.replace(days=+7)
    flask.session["begin_date"] = tomorrow.floor('day').isoformat()
    flask.session["end_date"] = nextweek.ceil('day').isoformat()
    flask.session["daterange"] = "{} - {}".format(
        tomorrow.format("MM/DD/YYYY"),
        nextweek.format("MM/DD/YYYY"))
    # Default time span each day, 8 to 5
    flask.session["begin_time"] = interpret_time("9am")
    flask.session["end_time"] = interpret_time("5pm")

def interpret_time( text ):
  """
  Read time in a human-compatible format and
  interpret as ISO format with local timezone.
  May throw exception if time can't be interpreted. In that
  case it will also flash a message explaining accepted formats.
  """
  app.logger.debug("Decoding time '{}'".format(text))
  time_formats = ["ha", "h:mma",  "h:mm a", "H:mm"]
  try: 
      as_arrow = arrow.get(text, time_formats).replace(tzinfo=tz.tzlocal())
      as_arrow = as_arrow.replace(year=2016) #HACK see below
      app.logger.debug("Succeeded interpreting time")
  except:
      app.logger.debug("Failed to interpret time")
      flask.flash("Time '{}' didn't match accepted formats 13:30 or 1:30pm"
            .format(text))
      raise
  return as_arrow.isoformat()


def interpret_date( text ):
  """
  Convert text of date to ISO format used internally,
  with the local time zone.
  """
  try:
    as_arrow = arrow.get(text, "MM/DD/YYYY").replace(
        tzinfo=tz.tzlocal())
  except:
      flask.flash("Date '{}' didn't fit expected format 12/31/2001")
      raise
  return as_arrow.isoformat()

def next_day(isotext):
  """
  ISO date + 1 day (used in query to Google calendar)
  """
  as_arrow = arrow.get(isotext)
  return as_arrow.replace(days=+1).isoformat()

####
#
#  Functions (NOT pages) that return some information
#
####

def create_display_intersected_times():
  """
  This function stores, in the session object, a nice 
  displayable list of the intersected free times amongst 
  all the current responders. 
  """
  for record in collection.find({ "type": "proposal", "_id": flask.session['proposal_id'] }):
      free_times = record['free_times']
  begin_date = arrow.get(flask.session['begin_date'])
  end_date = arrow.get(flask.session['end_date'])
  begin_time = arrow.get(flask.session['begin_time'])
  end_time = arrow.get(flask.session['end_time'])
  total = Agenda.timeSpanAgenda(begin_date, end_date, begin_time, end_time)
  for apt_list in free_times:
      agenda = Agenda.from_list(apt_list)
      total = total.intersect(agenda, desc="Available")
  total_list = total.to_list()
  flask.session['display_intersected'] = create_display_aptlist(total_list)

def create_display_responders():
  """
  This function stores, in the session object, a displayable list 
  of the names of all the current responders of this proposal. 
  """
  for record in collection.find({ "type": "proposal", "_id": flask.session['proposal_id'] }):
      responders = record['responders']
  flask.session['display_responders'] = responders
    
def create_display_meetinginfo():
  """
  This function stores, in the session object, a string containing 
  the date range of the meeting and a string containing the time 
  range of the proposed meeting. 
  """
  begin_date = arrow.get(flask.session['begin_date']).to('local')
  begin_date = begin_date.format('MM/DD/YYYY')
  end_date = arrow.get(flask.session['end_date']).to('local')
  end_date = end_date.format('MM/DD/YYYY')
  begin_time = arrow.get(flask.session['begin_time']).to('local')
  begin_time = begin_time.format('h:mm A')
  end_time = arrow.get(flask.session['end_time']).to('local')
  end_time = end_time.format('h:mm A')
  info_str1 = "Meeting date range is from " + begin_date + " to " + end_date + "."
  info_str2 = "Meeting time range is from " + begin_time + " to " + end_time + "."  
  flask.session['meeting_info1'] = info_str1
  flask.session['meeting_info2'] = info_str2


def create_display_aptlist(apt_list):
  """
  This function takes in a list of appointments and returns a list of strings representing
  the appointments, where the strings are suited for displaying. 
  Arguments:
      apt_list: a list of dictionaries either in the format of busy_list or in 
                the format of free_list 
                (see above for a detailed description of the format of busy_list and free_list)
  Returns: a list of strings representing appointments. 
  """
  display_apt_list = [] #list of dicts
  for apt in apt_list:
      info = {}
      if "id" in apt and apt['desc'] == "Available":
          info['id'] = apt['id']
      info['desc'] = apt['desc']
      apt_str = ""
      apt_str = apt_str + apt['desc'] + ": "
      apt_str = apt_str + convert(apt['begin']) + " - "
      apt_str = apt_str + convert(apt['end']) 
      info['display'] = apt_str
      display_apt_list.append(info)
      
  return display_apt_list
  
def list_calendars(service):
  """
  Given a google 'service' object, return a list of
  calendars.  Each calendar is represented by a dict.
  The returned list is sorted to have
  the primary calendar first, and selected (that is, displayed in
  Google Calendars web app) calendars before unselected calendars.
  """
  app.logger.debug("Entering list_calendars")  
  calendar_list = service.calendarList().list().execute()["items"]
  result = [ ]
  for cal in calendar_list:
      kind = cal["kind"]
      id = cal["id"]
      if "description" in cal: 
          desc = cal["description"]
      else:
          desc = "(no description)"
      summary = cal["summary"]
      # Optional binary attributes with False as default
      selected = ("selected" in cal) and cal["selected"]
      primary = ("primary" in cal) and cal["primary"]
      

      result.append(
        { "kind": kind,
          "id": id,
          "summary": summary,
          "selected": selected,
          "primary": primary
          })
  return sorted(result, key=cal_sort_key)


def cal_sort_key( cal ):
  """
  Sort key for the list of calendars:  primary calendar first,
  then other selected calendars, then unselected calendars.
  (" " sorts before "X", and tuples are compared piecewise)
  """
  if cal["selected"]:
     selected_key = " "
  else:
     selected_key = "X"
  if cal["primary"]:
     primary_key = " "
  else:
     primary_key = "X"
  return (primary_key, selected_key, cal["summary"])

@app.route("/show_sched")
def show_sched():
  free_busy = []
  for busy_dict in flask.session['busy_list']:
      free_busy.append(busy_dict)
  for free_dict in flask.session['free_list']:
      free_busy.append(free_dict)
  free_busy.sort(key=lambda r: r['begin']) #sort by begin date    
  
  flask.session['free_busy'] = create_display_aptlist(free_busy)
  return render_template('index.html')

@app.route("/calc_busy_free")
def calc_busy_free():

  #args
  calender_list = request.args.getlist('calender[]')
  flask.session['calender_list'] = calender_list

  find_free()
  find_busy()

def find_busy():
  
  #credentials
  credentials = client.OAuth2Credentials.from_json(flask.session['credentials'])
  service = get_gcal_service(credentials)

  busy_times = [] 
  credentials = client.OAuth2Credentials.from_json(flask.session['credentials'])
  service = get_gcal_service(credentials)
  for id in flask.session['calender_list']:
      events = service.events().list(calendarId=id, pageToken=None).execute()
      for event in events['items']:
          if ('transparency' in event) and event['transparency']=='transparent':
              continue 
          start_datetime = arrow.get(event['start']['dateTime'])
          end_datetime = arrow.get(event['end']['dateTime'])
          if overlap(start_datetime, end_datetime): 
            event_dict = {"desc":event['summary'], "begin":start_datetime.isoformat(), "end":end_datetime.isoformat()}
            busy_times.append(event_dict)

  busy_list = [] #list of strings
  for cal in busy_times:
      cal_dict = busy_times[cal]
      for conflict_event in cal_dict:
          busy_str = ""
          info_list = cal_dict[conflict_event]
          app.logger.debug(info_list)
          busy_str = busy_str + (info_list[0]) + ": "
          busy_str = busy_str + convert(info_list[1]) + " -  "
          busy_str = busy_str + convert(info_list[2])
          busy_list.append(busy_str)
  app.logger.debug(busy_list)
  flask.session['busy_list'] = busy_list

def find_free():

  busy_agenda = Agenda.from_list(flask.session['busy_list'])
      
  begin_date = arrow.get(flask.session['begin_date'])
  end_date = arrow.get(flask.session['end_date'])
  begin_time = arrow.get(flask.session['begin_time'])
  end_time = arrow.get(flask.session['end_time'])
  free_agenda = busy_agenda.complementTimeSpan(begin_date, end_date, begin_time, span_end_time)
  
  flask.session['free_list'] = free_agenda.to_list()

def delete_candidate():
  """
  This function creates a revised list of free times which contains only the free
  times with an id that is in flask.session['selected_candidates']. The revised
  list of free times is stored in flask.session['revised_free']. 
  """
  to_keep = flask.session['selected_candidates']
  revised_free = []
  for apt in flask.session['free_list']:
      if apt['id'] in to_keep:
          revised_free.append(apt)
  
  flask.session['revised_free'] = revised_free

def store_participant():
  """
  This function stores the participant's name and the participant's free times 
  in the database. 
  """
  collection.update({ "type": "proposal", "_id":flask.session['proposal_id'] }, {'$push': {'responders':flask.session['name']}})
  collection.update({ "type": "proposal", "_id":flask.session['proposal_id'] }, {'$push': {'free_times':flask.session['revised_free']}})
    
def store_proposer():
  """
  This function creates a random id to serve as the proposal id. 
  It then stores this proposal id, proposed meeting's start date, end date, 
  start time, end time, proposer's name, and proposer's free times in the database, 
  all in one record.
  """
  #collection.remove({})
  responders = []
  responders.append(flask.session['name'])
  free_times = []
  free_times.append(flask.session['revised_free'])
  proposal_id = str(ObjectId())
  flask.session['proposal_id'] = proposal_id
  record = { "type": "proposal",
         "_id": proposal_id,
         "start_date": flask.session['begin_date'], 
         "end_date": flask.session['end_date'],
         "start_time": flask.session['begin_time'],
         "end_time": flask.session['end_time'],
         "responders": responders,
         "free_times": free_times
        }
  collection.insert(record) 

def overlap(event_sdt, event_edt):

#sdt = start date time 
#edt = end date time 
  event_sd = event_sdt.date()
  event_ed = event_edt.date()
  event_st = event_sdt.time()
  event_et = event_edt.time()
  desired_sd= arrow.get(flask.session['begin_date']).date()
  desired_ed = arrow.get(flask.session['end_date']).date()
  desired_st = arrow.get(flask.session['begin_time']).time()
  desired_et = arrow.get(flask.session['end_time']).time()
  if not (desired_sd <= event_sd <= desired_ed) or not (desired_sd <= event_ed <= desired_ed):
      return False 
  elif (event_et <= desired_st):
      return False 
  elif (event_st >= desired_et):
      return False
  else:
      return True


def convert(date_time):

  arrow_date_time = arrow.get(date_time)
  local_arrow = arrow_date_time.to('local')
  formatted_str = local_arrow.format('MM/DD/YYYY h:mm A')
  return formatted_str

#################
#
# Functions used within the templates
#
#################

@app.template_filter( 'fmtdate' )
def format_arrow_date( date ):
    try: 
        normal = arrow.get( date )
        return normal.format("ddd MM/DD/YYYY")
    except:
        return "(bad date)"

@app.template_filter( 'fmttime' )
def format_arrow_time( time ):
    try:
        normal = arrow.get( time )
        return normal.format("HH:mm")
    except:
        return "(bad time)"
    
#############


if __name__ == "__main__":
  # App is created above so that it will
  # exist whether this is 'main' or not
  # (e.g., if we are running under green unicorn)
  app.run(port=CONFIG.PORT,host="0.0.0.0")
    
