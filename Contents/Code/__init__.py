# MythRecordings plug-in for Plex
# Copyright (C) 2013 Thomas Schaumburg
#
# This code is heavily inspired by the NextPVR bundle by David Cole.

import xml.etree.ElementTree as ET
import datetime
import urllib2
import json
####################################################################################################
VIDEO_PREFIX = "/video/mythrecordings"

NAME = "MythTV recordings"
ART  = 'item-default.png'
BY_NAME  = 'by-name.png'
BY_DATE  = 'by-date.png'
BY_CATEGORY  = 'by-category.png'
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
    showByRecordingGroup = Prefs['showByRecordingGroup']
    showByChannelName = Prefs['showByChannelName']
    
    dir=ObjectContainer()
    dir.add(DirectoryObject(key=Callback(GroupRecordingsBy, filterKeyNames=[], filterKeyValues=[], groupKeyNames=['Title']), title='By title', thumb=R(BY_NAME)))
    dir.add(DirectoryObject(key=Callback(GroupRecordingsBy, filterKeyNames=[], filterKeyValues=[], groupKeyNames=['Category', 'Title'], aliasPrefName = 'categoryAliases', iconPrefix = 'CategoryIcon_', backgroundPrefix = 'CategoryBackground_'), title='By category', thumb=R(BY_CATEGORY)))
    if showByRecordingGroup:
        dir.add(DirectoryObject(key=Callback(GroupRecordingsBy, filterKeyNames=[], filterKeyValues=[], groupKeyNames=['Recording/RecGroup']), title='By recording group'))
    if showByChannelName:
        dir.add(DirectoryObject(key=Callback(GroupRecordingsBy, filterKeyNames=[], filterKeyValues=[], groupKeyNames=['Channel/ChannelName']), title='By channel'))
    dir.add(DirectoryObject(key=Callback(GetRecordingList, filterKeyNames=[], filterKeyValues=[], sortKeyName='StartTime'), title='By recording date', thumb=R(BY_DATE)))
    dir.add(PrefsObject(title="Preferences", summary="Configure how to connect to the MythTV backend", thumb=R("icon-prefs.png")))
    return dir


####################################################################################################
# GroupRecordingsBy:
# ==================
# Create a directory (ObjectContainer) listing the recordings grouped by key (the value of the 
# element identified by the XPATH expression in the keyName parameter).
#
# The key thus found is passed through an aliasing mechanism, intended to conflate almost-identical
# values (like "Series" and "Serie" or "Tonight Show" and "The Tonight Show"). See the LoadAliases
# function for details.
#
# If iconPrefix or backgroundPrefix is specified, each entry in the directory (ObjectContainer)
# will have an icon (thumb) or background image (art) associated with it. These images will be
# loaded from MythRecordings.bundle/Contents/Resources/${iconPrefix}${key}.png and 
# MythRecordings.bundle/Contents/Resources/${backgroundPrefix}${key}.png respectively. 
####################################################################################################
@route('/video/mythrecordings/GroupRecordingsBy', filterKeyNames = list, filterKeyValues = list, groupKeyNames = list, allow_sync=True) 
def GroupRecordingsBy(groupKeyNames, filterKeyNames = [], filterKeyValues = [], aliasPrefName = None, iconPrefix = '', backgroundPrefix = '', backgroundName = ''):
	if groupKeyNames is None:
		groupKeyNames = []

	if filterKeyNames is None:
		filterKeyNames = []

	if filterKeyValues is None:
		filterKeyValues = []

	if len(filterKeyValues) != len(filterKeyNames):
		raise(Exception('Code error: filter key name and value lists should be of equal length'))

	if len(groupKeyNames)==0:
		return GetRecordingList(filterKeyNames=filterKeyNames, filterKeyValues=filterKeyValues, aliasPrefName=aliasPrefName, sortKeyName='StartTime', backgroundName = backgroundName)

	keyName = groupKeyNames[0]
	del groupKeyNames[0]
	
	if len(filterKeyNames) == 0:
		title = 'By %s' % keyName
	else:
		title = ""
		for n in range(0, len(filterKeyNames)):
			keyN = filterKeyNames[n]
			valueN = filterKeyValues[n]
			title = title + ', %s "%s"' % (keyN, valueN)
		title = title + ', by %s' % keyName
		title = title[2:] # remove starting ", "

	oc = ObjectContainer(title2=title) # title1 is not displayed (on most clients, anyway)
	
	# Load aliases from preferences:
	keyAliases = LoadAliases(aliasPrefName)

	url = PVR_URL + 'Dvr/GetRecordedList'
	Log('GroupRecordingsBy(keyName="%s", filterKeyNames="%s", filterKeyValues="%s"): Loading URL %s' % (keyName,filterKeyNames,filterKeyValues,url))
	request = urllib2.Request(url, headers={"Accept" : "application/xml"})
	u = urllib2.urlopen(request)
	tree = ET.parse(u)
	root = tree.getroot()
	
	# Loop through recordings, collection all unique values of keyName:
	recordings = root.findall('Programs/Program')
	alreadyAdded = []
	for recording in recordings:
		if recording.find('Recording/RecGroup').text == 'Deleted':
			continue
		if recording.find('Recording/RecGroup').text == 'LiveTV':
			continue
		if not Match(filterKeyNames, filterKeyValues, recording, keyAliases):
			continue

		orgKeyValue = recording.find(keyName).text
		keyValue = MapAliases(orgKeyValue, keyAliases)

		if keyValue not in alreadyAdded:
			Log('GroupRecordings: orgKeyValue = %s, keyValue = %s' % (orgKeyValue, keyValue))
			subFilterKeyNames = list(filterKeyNames)
			subFilterKeyNames.append(keyName)
			subFilterKeyValues = list(filterKeyValues)
			subFilterKeyValues.append(keyValue)

			alreadyAdded.append(keyValue)
			iconName = '%s%s.png' % (iconPrefix, keyValue)
			Log('iconName = %s' % iconName)
			backgroundName = '%s%s.png' % (backgroundPrefix, keyValue)
			Log('backgroundName = %s' % backgroundName)

			oc.add(DirectoryObject(key=Callback(GroupRecordingsBy, filterKeyNames=subFilterKeyNames, filterKeyValues=subFilterKeyValues, groupKeyNames=groupKeyNames, aliasPrefName=aliasPrefName, iconPrefix=iconPrefix, backgroundPrefix=backgroundPrefix, backgroundName=backgroundName), title=keyValue, thumb=R(iconName), art=R(backgroundName)))
		
	oc.objects.sort(key=lambda obj: obj.title)
	return oc

def Match(filterKeyNames, filterKeyValues, recording, keyAliases):
	for n in range(0, len(filterKeyNames)):
		filterKeyName = filterKeyNames[n]
		filterKeyValue = filterKeyValues[n]
		actualFilterKeyValue = recording.find(filterKeyName).text
		Log("filterKeyValue=%s, actualFilterKeyValue=%s"%(filterKeyValue, actualFilterKeyValue))
		actualFilterKeyValue = MapAliases(actualFilterKeyValue, keyAliases)
		Log("filterKeyValue=%s, actualFilterKeyValue=%s"%(filterKeyValue, actualFilterKeyValue))
		if not actualFilterKeyValue == filterKeyValue:
			Log("Match (filterKeyName=%s, filterKeyValue=%s, actualFilterKeyValue=%s) = False" % (filterKeyName, filterKeyValue, actualFilterKeyValue))
			return False
	Log("Match(filterKeyNames=%s, filterKeyValues=%s) = True" % (filterKeyNames, filterKeyValues))
	return True

####################################################################################################
# GetRecordingList:
# =================
# Creates a directory (ObjectContainer) listing all the recordings where the contents of the element
# identified by the filterKeyNames parameter (a lis of XPATH expressions) matches filterKeyValues. The
# values are subject to the same aliasing mechanism described for GroupRecordingsBy above.
# 
# The resulting list of recordings is sorted by the element identified by the sortKeyName parameter
# (another XPATH expression)
####################################################################################################
@route('/video/mythrecordings/GetRecordingList', filterKeyNames=list, filterKeyValues=list, allow_sync=True)
def GetRecordingList(filterKeyNames, filterKeyValues, sortKeyName = None, aliasPrefName = '', sortReverse = True, backgroundName = ''):
	url = PVR_URL + 'Dvr/GetRecordedList'
	Log('GetRecordingList(filterKeyNames="%s", filterKeyValues="%s", sortKeyName="%s, aliasPrefName = %s"): Loading URL %s' % (filterKeyNames, filterKeyValues, sortKeyName, aliasPrefName, url))

	keyAliases = LoadAliases(aliasPrefName)

	title2= "By title"
	if not filterKeyValues is None:
		title2 = " - ".join(filterKeyValues)

	oc = ObjectContainer(title2 = title2)

	if not backgroundName == '':
		oc.art = R(backgroundName)

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
		if recording.find('Recording/RecGroup').text == 'LiveTV':
			continue
		if recording.find('Title').text == 'Unknown':
			continue
		if not Match(filterKeyNames, filterKeyValues, recording, keyAliases):
			continue
		oc.add(Recording(recording, backgroundName))
			
	return oc


####################################################################################################
# LoadAliases:
# ============
# Loads a list of aliases from the preferences string specified by the parameter aliasPrefName.
#
# The alias list if a JSON formatted list of list of strings. Each list-of-strings is interpreted
# as a canonical name, followed by its synonyms.
#
# Example:
#    The following JSON formatted alias string defines the canonical names 'Series' and 'Movies', 
#    and two synonyms for each:
#       [['Series', 'serie', 'series'], ['Movies', 'film', 'action']]
####################################################################################################
def LoadAliases(aliasPrefName):
	if aliasPrefName is None:
		return []
	if aliasPrefName == "":
		return []
	keyAliasString = Prefs[aliasPrefName]
	try:
		Log('keyAliasString = %s', keyAliasString)
		keyAliases = json.loads(keyAliasString)
		Log('keyAliases = %s', keyAliases)
	except:
		keyAliases = [] # no aliases, then

	return keyAliases


####################################################################################################
# MapAlias:
# =========
# Maps a string into its canonical version (if any), using an alias list loaded by LoadAliases.
#
# Example:
#    Assume the JSON formatted alias string from the LoadAliases description:
#       [['Series', 'serie', 'series'], ['Movies', 'film', 'action']]
#    This will produce the following mappings:
#       'action' => 'Movies'
#       'Movies' => 'Movies'
#       'serie'  => 'Series'
#       'xyz'    => 'xyz'
#    Note how a string that doesn't appear in as a synonym ('xyz' above) is passed through
#    unchanged.
####################################################################################################
def MapAliases(keyValue, keyAliases):
	if keyValue is None:
		keyValue = ''

	result = keyValue
	
	#Log('type(keyAliases) = %s', type(keyAliases))
	if isinstance(keyAliases, list): 
		for aliasList in keyAliases:
			#Log('Looking for %s in %s', keyValue, aliasList)
			if (keyValue in aliasList):
				#Log('Mapping %s => %s', keyValue, aliasList[0])
				result = aliasList[0]

	return result


####################################################################################################
def Recording(recording, backgroundName = ''):
	
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
		epname = "%s (%s)" % (epname, shouldStart.strftime('%Y-%m-%d %H:%M'))
	except:
		Warning('Recording: Recording: "%s" had no SubTitle - using date' % showname)
		epname = shouldStart.strftime('%Y-%m-%d')

	# Still recording?
	# ================

	utcnow = datetime.datetime.utcnow()
	timeSinceEnd = utcnow - didEnd
	stillRecording = timeSinceEnd < datetime.timedelta(hours=0, minutes=0,seconds=30)

	# Duration:
	# =========

	try:
		if stillRecording:
			delta = didEnd - didStart
		else:
			delta = shouldEnd - didStart + datetime.timedelta(hours=0, minutes=5,seconds=0)

	except:
		Warning('Recording: Recording: "%s", Duration error, Unexpected error' % showname)
		delta = datetime.timedelta(hours=3, minutes=0,seconds=0)

	duration = str(int(delta.seconds * 1000))
	
	# Check for missing start or end:
	# ===============================

	try:
		missedAtStart = didStart - shouldStart # negative means OK
		missedAtEnd = shouldEnd - didEnd # negative means OK
		# generate warning:
		missedStart = missedAtStart > datetime.timedelta(hours=0, minutes=0,seconds=0)
		missedEnd = missedAtEnd > datetime.timedelta(hours=0, minutes=0,seconds=0)

		if stillRecording:
			missedEnd = False

		if (missedStart and missedEnd):
			warning = 'WARNING: Recording may have missed both start and end of program (by %s and %s, respectively)\n' % (str(missedAtStart),str(missedAtEnd))
		elif (missedStart):
			warning = 'WARNING: Recording may have missed start of program by %s\n' % str(missedAtStart)
		elif (missedEnd):
			warning = 'WARNING: Recording may have missed end of program by %s\n' % str(missedAtEnd)
		else:
			warning = ""

		if stillRecording:
			warning = 'STILL RECORDING\n' + warning

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
	if stillRecording:
		header = header + " (STILL RECORDING)"

	# Screenshot:
	# ===========
	if not channel is None and not recordingStart is None:
		thumb = PVR_URL + '/Content/GetPreviewImage?ChanId=%s&StartTime=%s' % (channel, recordingStart,)
	else:
		thumb = R(ART)


	return VideoClipObject(
                title = header,
                summary = str(warning) + str(descr),
                originally_available_at = shouldStart,
                thumb = thumb,
		art = R(backgroundName),
		duration = int(duration),
		key = Callback(RecordingInfo, chanId=chanId, startTime=recordingStart, backgroundName=backgroundName),
		rating_key= str(int(shouldStart.strftime('%Y%m%d%H%M'))),
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
def RecordingInfo(chanId, startTime, backgroundName):
	url = PVR_URL + 'Dvr/GetRecorded?StartTime=%s&ChanId=%s' % (startTime, chanId)
	request = urllib2.Request(url, headers={"Accept" : "application/xml"})
	Log('RecordingInfo(chanId="%s", startTime="%s"): opening %s' % (chanId, startTime, url))
	u = urllib2.urlopen(request)
	tree = ET.parse(u)
	root = tree.getroot()

	recording = root #.findall('Programs/Program')

	recording_object = Recording(recording, backgroundName)
	return ObjectContainer(objects=[recording_object], art=R(backgroundName))

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
