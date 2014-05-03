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
    dir.add(DirectoryObject(key=Callback(GroupRecordingsBy, keyName='Title'), title='Recordings by title'))
    dir.add(DirectoryObject(key=Callback(GroupRecordingsBy, keyName='Category'), title='Recordings by category'))
    dir.add(DirectoryObject(key=Callback(GroupRecordingsBy, keyName='Recording/RecGroup'), title='Recordings by recording group'))
    dir.add(DirectoryObject(key=Callback(GroupRecordingsBy, keyName='Channel/ChannelName'), title='Recordings by channel'))
    dir.add(DirectoryObject(key=Callback(GetRecordingList, filterKeyName=None, filterKeyValue=None, sortKeyName='StartTime'), title='Recordings by recording date'))
    dir.add(PrefsObject(title="Preferences", summary="Configure how to connect to the MythTV backend", thumb=R("icon-prefs.png")))
    return dir

####################################################################################################
@route('/video/mythrecordings/GroupRecordingsBy', allow_sync=True) 
def GroupRecordingsBy(keyName):
	oc = ObjectContainer(title2='By %s' % keyName)

	url = PVR_URL + 'Dvr/GetRecordedList'
	Log('GroupRecordingsBy(keyName="%s"): Loading URL %s' % (keyName,url))
	request = urllib2.Request(url, headers={"Accept" : "application/xml"})
	u = urllib2.urlopen(request)
	tree = ET.parse(u)
	root = tree.getroot()
	
	# Loop through recordings, collection all unique values of keyName:
	recordings = root.findall('Programs/Program')
	alreadyAdded = []
	for recording in recordings:
		keyValue = recording.find(keyName).text
		if keyValue not in alreadyAdded:
			alreadyAdded.append(keyValue)
			oc.add(DirectoryObject(key=Callback(GetRecordingList, filterKeyName=keyName, filterKeyValue=keyValue, sortKeyName='StartTime'), title=keyValue))
		
	oc.objects.sort(key=lambda obj: obj.title)
	return oc

####################################################################################################
@route('/video/mythrecordings/GetRecordingList', allow_sync=True)
def GetRecordingList(filterKeyName, filterKeyValue, sortKeyName = None, sortReverse = True):
	oc = ObjectContainer(title2=filterKeyValue)

	url = PVR_URL + 'Dvr/GetRecordedList'
	Log('GetRecordingList(filterKeyName="%s", filterKeyValue="%s", sortKeyName="%s"): Loading URL %s' % (filterKeyName, filterKeyValue, sortKeyName, url))
	request = urllib2.Request(url, headers={"Accept" : "application/xml"})
	u = urllib2.urlopen(request)
	tree = ET.parse(u)
	root = tree.getroot()
	
	recordings = root.findall('Programs/Program')
	if (sortKeyName is not None):
		recordings.sort(key=lambda rec: rec.find(sortKeyName).text, reverse=sortReverse)
	
	for recording in recordings:
		if recording.find('Recording/RecGroup').text == 'Deleted':
			continue
		title = recording.find('Title').text
		if (not title == "Unknown"):
			if (filterKeyName is None):
				oc.add(Recording(recording))
			else:
				actualKeyValue = recording.find(filterKeyName).text
				if actualKeyValue == filterKeyValue:
					oc.add(Recording(recording))
	return oc

####################################################################################################
def Recording(recording):
	
	# Mandatory properties: Title, Channel, StartTime, EndTime:
	# =========================================================

	showname = recording.find('Title').text
	chanId = recording.find('Channel').find('ChanId').text
	programStart = recording.find('StartTime').text
	programEnd = recording.find('EndTime').text
	recordingStart = recording.find('Recording/StartTs').text
	recordingEnd = recording.find('Recording/EndTs').text

	shouldStart = datetime.datetime.strptime(programStart,"%Y-%m-%dT%H:%M:%SZ")
	didStart = datetime.datetime.strptime(recordingStart,"%Y-%m-%dT%H:%M:%SZ")
	shouldEnd = datetime.datetime.strptime(programEnd,"%Y-%m-%dT%H:%M:%SZ")
	didEnd = datetime.datetime.strptime(recordingEnd,"%Y-%m-%dT%H:%M:%SZ")

	fileName = recording.find('FileName').text
	storageGroup = recording.find('Recording/StorageGroup').text

	# Playback URL:
	# =============
	# MythTV setting 'Master Backend Override'definition: If enabled, the master backend will stream and 
	# delete files if it finds them in the video directory. Useful if you are using a central storage 
	# NFS share, and your slave backend isn’t running.
	#
	# Note from user sammyjayuk on the Plex forums: GetRecording doesn't respect this setting (it sends
	# an HTTP redirect sending you to the recording backend). GetFile works as expected.
	#
	# For experimental purposes, we'll use GetFile, but only if the user sets this in the settings.
	respectMasterBackendOverride = Prefs['respectMasterBackendOverride']
	
	if respectMasterBackendOverride:
		testURL = PVR_URL + 'Content/GetFile?StorageGroup=%s&FileName=%s' % (storageGroup,fileName,)
	else:
		testURL = PVR_URL + 'Content/GetRecording?ChanId=%s&StartTime=%s' % (chanId,recordingStart,)
	
	Log('Recording: Name "%s" => URL="%s"' % (showname, testURL))


	# Optional properties:
	# ====================	

	
	# SubTitle:
	# =========

	try:
		epname = recording.find('SubTitle').text
	except:
		Warning('Recording: Recording: "%s" had no SubTitle - using date' % showname)
		epname = airdate.strftime('%Y-%m-%d')


	# Duration:
	# =========
	try:
		airdate = shouldStart
		delta = didEnd - didStart
		duration = str(int(delta.seconds * 1000))

	except:
		Warning('Recording: Recording: "%s", Duration error, Unexpected error' % showname)
		delta = datetime.timedelta(hours=3, minutes=0,seconds=0)
	
	# Check for missing start or end:
	# ===============================

	try:
		missedAtStart = didStart - shouldStart # negative means OK
		missedAtEnd = shouldEnd - didEnd # negative means OK
		# generate warning:
		missedStart = missedAtStart > datetime.timedelta(hours=0, minutes=0,seconds=0)
		missedEnd = missedAtEnd > datetime.timedelta(hours=0, minutes=0,seconds=0)

		if (missedStart and missedEnd):
			warning = 'WARNING: Recording may have missed both start and end of program (by %s and %s, respectively)\n' % (str(missedAtStart),str(missedAtEnd))
		elif (missedStart):
			warning = 'WARNING: Recording may have missed start of program by %s\n' % str(missedAtStart)

		elif (missedStart and missedEnd):
			warning = 'WARNING: Recording may have missed end of program by %s\n' % str(missedAtEnd)
		else:
			warning = ""

	except:

		Warning('Recording: Recording: "%s", Duration error, Unexpected error' % showname)
		
	# Description:
	# ============
	try:
		descr = recording.find('Description').text.strip()
	except:
		Warning('Recording: Recording: "%s", Descr error, Unexpected error' % showname)
		descr = None


	# ChanId:
	# =======
	try:
		channel = recording.find('Channel').find('ChanId').text
		if channel == '0':

			channel = None
	except:
		Warning('Recording: Recording: "%s", Could not set channel ID' % showname)			
		channel = None
	
	# Title:
	# ======
	header = '%s - %s' % (showname,epname)
	if epname is None:
		header = showname

	# Screenshot:
	# ===========
	if not channel is None and not recordingStart is None:
		thumb = PVR_URL + '/Content/GetPreviewImage?ChanId=%s&StartTime=%s' % (channel, recordingStart,)
	else:
		thumb = R(ART)


	return VideoClipObject(
                title = header,
                summary = str(warning) + str(descr),
                originally_available_at = airdate,
                thumb = thumb,
		duration = int(duration),
		key = Callback(RecordingInfo, chanId=chanId, startTime=recordingStart),
		rating_key= str(int(airdate.strftime('%Y%m%d%H%M'))),
		items = [
			MediaObject(
				parts = [
					PartObject(key=testURL, duration=int(duration))
				],
				duration = int(duration),
				container = 'mp2ts',
				#video_codec = VideoCodec.H264,
				#audio_channels = 2,
				optimized_for_streaming = True
			)
		]
        )

####################################################################################################
@route('/video/mythrecordings/GetRecordingInfo', allow_sync=True)
def RecordingInfo(chanId, startTime):
	url = PVR_URL + 'Dvr/GetRecorded?StartTime=%s&ChanId=%s' % (startTime, chanId)
	request = urllib2.Request(url, headers={"Accept" : "application/xml"})
	Log('RecordingInfo(chanId="%s", startTime="%s"): opening %s' % (chanId, startTime, url))
	u = urllib2.urlopen(request)
	tree = ET.parse(u)
	root = tree.getroot()

	recording = root #.findall('Programs/Program')

	recording_object = Recording(recording)
	return ObjectContainer(objects=[recording_object])

#####################################################################################################
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
