# MythRecordings plug-in for Plex
# Copyright (C) 2013 Thomas Schaumburg
#
# This code is heavily inspired by the NextPVR bundle by David Cole.

import xml.etree.ElementTree as ET
import datetime
import urllib2
####################################################################################################
VIDEO_PREFIX = "/video/mythrecordings"

NAME = "MythTV recordings"
ART  = 'item-default.png'
PVR_URL = 'http://%s:%s/' % (Prefs['server'],Prefs['port'])
####################################################################################################

def Start():
    
	ObjectContainer.title1 = NAME
	Log('%s Started' % NAME)
	Log('URL set to %s' % PVR_URL)
	ValidatePrefs()

####################################################################################################
# This main function will setup the displayed items.
@handler('/video/mythrecordings','MythTV recordings')
def MainMenu():
	
    dir=ObjectContainer()
    Log('MainMenu: Adding By-category Menu')
    #dir.add(DirectoryObject(key=Callback(RecordingsByTitle), title='Recordings by title'))
    dir.add(DirectoryObject(key=Callback(RecordingsByKey, groupBy='Title'), title='Recordings by title'))
    Log('MainMenu: Adding By-title Menu')
    dir.add(DirectoryObject(key=Callback(RecordingsByKey, groupBy='Category'), title='Recordings by category'))
    Log('MainMenu: Adding By-date Menu')
    dir.add(DirectoryObject(key=Callback(RecordingsByDate), title='Recordings by recording date'))

    dir.add(PrefsObject(title="Preferences", summary="Configure how to connect to the MythTV backend", thumb=R("icon-prefs.png")))
    Log('MainMenu: URL set to %s' % PVR_URL)
    return dir

####################################################################################################
@route('/video/mythrecordings/bykey')
def RecordingsByKey(groupBy):
	Log('RecordingsByKey: Generating Recordings Screen')
	oc = ObjectContainer(title2='By title')
	Log('RecordingsByKey: Calling Recording List')
	url = PVR_URL + 'Dvr/GetRecordedList'
	Log('RecordingsByKey: Loading URL %s' % url)
	request = urllib2.Request(url, headers={"Accept" : "application/xml"})
	Log('RecordingsByKey: Request: %s' % request)
	u = urllib2.urlopen(request)
	Log('RecordingsByKey: Result = %s code= %s' % ( u.code,u.msg))
	tree = ET.parse(u)
	root = tree.getroot()
	
	# Nodes with start_time > stime which is x number of days ago
	recordings = root.findall('Programs/Program')
	shows = []
	for recording in recordings:
		Log('RecordingsByKey: **********************************************************************')
		groupByValue = recording.find(groupBy).text
		Log('RecordingsByKey: Recording id %s name is \'%s\'' % (recording.find('ProgramId').text,groupByValue))
		if groupByValue not in shows:
			Log('RecordingsByKey: Adding %s to showset and Directory' % groupByValue)
			shows.append(groupByValue)
			oc.add(DirectoryObject(key=Callback(AddSeriesObject2, groupByValue=groupByValue, groupByKey=groupBy), title=groupByValue))
		
	
	oc.objects.sort(key=lambda obj: obj.title)
	Log('RecordingsByKey: Finished adding Episodes')		
	return oc

####################################################################################################
def AddSeriesObject2(groupByValue, groupByKey):
	oc = ObjectContainer(title2=groupByValue)
	url = PVR_URL + 'Dvr/GetRecordedList'
	Log('AddSeriesObject: Loading URL %s' % url)
	request = urllib2.Request(url, headers={"Accept" : "application/xml"})
	Log('Request: %s' % request)
	u = urllib2.urlopen(request)
	Log('AddSeriesObject: Result = %s code= %s' % ( u.code,u.msg))
	tree = ET.parse(u)
	root = tree.getroot()
	Log('Root = %s'  %  root)
	
	recordings = root.findall('Programs/Program')
	recordings.sort(key=lambda rec: rec.find('StartTime').text,reverse=True)
	for recording in recordings:
		showname = recording.find(groupByKey).text
		if showname == groupByValue:
			oc.add(ConvertRecordingToEpisode(recording))

	#oc.objects.sort(key=lambda obj: obj.rating_key,reverse=False)
	return oc

####################################################################################################
@route('/video/mythrecordings/bydate')
def RecordingsByDate():
	Log('RecordingsByDate: Generating Recordings Screen')
	oc = ObjectContainer(title2='By date')
	Log('RecordingsByDate: Calling Recording List')
	url = PVR_URL + 'Dvr/GetRecordedList'
	Log('RecordingsByDate: Loading URL %s' % url)
	request = urllib2.Request(url, headers={"Accept" : "application/xml"})
	Log('RecordingsByDate: Request: %s' % request)
	u = urllib2.urlopen(request)
	Log('RecordingsByDate: Result = %s code= %s' % ( u.code,u.msg))
	tree = ET.parse(u)
	root = tree.getroot()
	
	# Nodes with start_time > stime which is x number of days ago
	recordings = root.findall('Programs/Program')
	recordings.sort(key=lambda rec: rec.find('StartTime').text,reverse=True)
	shows = []
	for recording in recordings:
		Log('RecordingsByDate: **********************************************************************************************************')
		oc.add(ConvertRecordingToEpisode(recording))		
	
	Log('RecordingsByDate: Finished adding Episodes')		
	return oc

####################################################################################################
def ConvertRecordingToEpisode(recording):
	Log('**********************************************************************************************************')
	
	# Mandatory properties: Title, Channel, StartTime, EndTime:
	# =========================================================
	showname = recording.find('Title').text
	chanId = recording.find('Channel').find('ChanId').text
	programStart = recording.find('StartTime').text
	programEnd = recording.find('EndTime').text
	recordingStart = recording.find('Recording/StartTs').text
	recordingEnd = recording.find('Recording/EndTs').text
	# calculated:
	shouldStart = datetime.datetime.strptime(programStart,"%Y-%m-%dT%H:%M:%SZ")
	didStart = datetime.datetime.strptime(recordingStart,"%Y-%m-%dT%H:%M:%SZ")
	shouldEnd = datetime.datetime.strptime(programEnd,"%Y-%m-%dT%H:%M:%SZ")
	didEnd = datetime.datetime.strptime(recordingEnd,"%Y-%m-%dT%H:%M:%SZ")


	testURL = PVR_URL + 'Content/GetRecording?ChanId=%s&StartTime=%s' % (chanId,recordingStart,)
	Log('ConvertRecordingToEpisode: Name  "%s" URL="%s"' % (showname,testURL))

	# Optional properties:
	# ====================	
	
	# SubTitle:
	# =========
	try:
		epname = recording.find('SubTitle').text
	except:
		Warning('ConvertRecordingToEpisode: Recording: "%s" had no SubTitle - using date' % showname)
		epname = airdate.strftime('%Y-%m-%d')

	# Duration:
	# =========
	try:
		airdate = shouldStart
		delta = didEnd - didStart
	except:
		Warning('ConvertRecordingToEpisode: Recording: "%s", Duration error, Unexpected error' % showname)
		delta = datetime.timedelta(hours=3, minutes=0,seconds=0)
	
	if not delta is None:
		Log('ConvertRecordingToEpisode: Duration Set to "%d" seconds' % delta.seconds)
	else:
		Log('ConvertRecordingToEpisode: Duration Set is empty')

	# Check for missing start or end:
	# ===============================
	try:
		missedAtStart = didStart - shouldStart # negative means OK
		missedAtEnd = shouldEnd - didEnd # negative means OK
		# generate warning:
		missedStart = missedAtStart > datetime.timedelta(hours=0, minutes=0,seconds=0)
		missedEnd = missedAtEnd > datetime.timedelta(hours=0, minutes=0,seconds=0)
		if (missedStart and missedEnd):
			warning = 'WARNING: Recording may have missed both start and end of program (by %s and %s, respectively)' % (str(missedAtStart),str(missedAtEnd))
		elif (missedStart):
			warning = 'WARNING: Recording may have missed start of program by %s' % str(missedAtStart)
		elif (missedStart and missedEnd):
			warning = 'WARNING: Recording may have missed end of program by %s' % str(missedAtEnd)
		else:
			warning = None
	except:
		Warning('ConvertRecordingToEpisode: Recording: "%s", Duration error, Unexpected error' % showname)
		
	# Description:
	# ============
	try:
		descr = recording.find('Description').text.strip()
	except:
		Warning('ConvertRecordingToEpisode: Recording: "%s", Descr error, Unexpected error' % showname)
		descr = None
	Log('ConvertRecordingToEpisode: Desc Set to "%s"' % descr)

	# ChanId:
	# =======
	try:
		channel = recording.find('Channel').find('ChanId').text
		if channel == '0':
			channel = None
	except:
		Warning('ConvertRecordingToEpisode: Recording: "%s", Could not set channel ID' % showname)			
		channel = None
	if not channel is None:
		Log('ConvertRecordingToEpisode: Channel ID set to "%s"' % channel)
	
	header = '%s - %s' % (showname,epname)
	if epname is None:
		header = showname

	return CreateVideoObject(
		url=testURL,
		title= header,
		summary=descr,
		recordingStart=recordingStart,
		warning=warning,
		rating_key=str(int(airdate.strftime('%Y%m%d%H%M'))),
		originally_available_at=airdate.strftime('%c'),
		duration=str(int(delta.seconds * 1000)),
		channel=channel
	)

####################################################################################################
#@route('/video/mythrecordings/videoobject')
def CreateVideoObject(url, title, summary, rating_key, warning=None, recordingStart=None, originally_available_at=None, duration=None, channel=None, include_container=False):
	Log('Date %s ' % originally_available_at)

	if int(duration) <1:
		duration = '50'

	if warning is None:
		warning = ''
	else:
		warning = '\n' + str(warning)

	#if not channel is None:
	#	thumb = PVR_URL + 'Guide/GetChannelIcon?ChanId=%s' % channel
	#else:
	#	thumb = R(ART)
	if not channel is None and not recordingStart is None:
		thumb = PVR_URL + 'Content/GetPreviewImage?ChanId=%s&StartTime=%s' % (channel, recordingStart,)
	else:
		thumb = R(ART)

	Log('EpisodeObject(title="%s")' % title)
	track_object = EpisodeObject(
		key = Callback(CreateVideoObject, url=url, title=title, summary=summary, rating_key=rating_key, recordingStart=recordingStart, warning=warning, originally_available_at=originally_available_at, duration=duration, channel=channel, include_container=True),
		title = title,
		summary = str(summary) + str(warning),
		originally_available_at = Datetime.ParseDate(originally_available_at),
		duration = int(duration),
		rating_key=int(rating_key),
		thumb = thumb,
		items = [
			MediaObject(
				parts = [
					PartObject(key=url, duration=int(duration))
				],
				duration = int(duration),
				container = 'mp2ts',
				#video_codec = VideoCodec.H264,
				#audio_channels = 2,
				optimized_for_streaming = True
			)
		]
	)

	if include_container:
		return ObjectContainer(objects=[track_object])
	else:
		return track_object

####################################################################################################
def ValidatePrefs():
	global PVR_URL
	if Prefs['server'] is None:
		return MessageContainer("Error", "No server information entered.")
	elif Prefs['port'] is None:
		return MessageContainer("Error", "Server port is not defined")
	elif not Prefs['port'].isdigit():
		return MessageContainer("Error", "Server port is not numeric")
	else:
		port = Prefs['port']
		PVR_URL = 'http://%s:%s/' % (Prefs['server'],port)
		Log('ValidatePrefs: PVR URL = %s' % PVR_URL)
		return MessageContainer("Success","Success")
