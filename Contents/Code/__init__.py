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
TITLE_SPLITTERS = ['-', ':']
####################################################################################################

def Start():
    
	ObjectContainer.title1 = NAME
	Log('%s Started' % NAME)
	Log('URL set to %s' % PVR_URL)
	ValidatePrefs()

####################################################################################################
# MainMenu:
# =========
# Sets up the top-level menu.
#
# Returns:
#    ObjectContainer
####################################################################################################
@handler('/video/mythrecordings','MythTV recordings')
def MainMenu():
    dir=ObjectContainer()

    # By title:
    dir.add(
        DirectoryObject(
            key=Callback(GroupRecordingsBy, filterKeyNames=[], filterKeyValues=[], groupKeyNames=['Title']), 
            title='By title', 
            thumb=R(BY_NAME)
        )
    )
    
    # By category, then by title:
    dir.add(
        DirectoryObject(
            key=Callback(GroupRecordingsBy, filterKeyNames=[], filterKeyValues=[], groupKeyNames=['Category', 'Title']), 
            title='By category', 
            thumb=R(BY_CATEGORY)
        )
    )

    # By recording group:
    showByRecordingGroup = Prefs['showByRecordingGroup']
    if showByRecordingGroup:
        dir.add(
            DirectoryObject(
                key=Callback(GroupRecordingsBy, filterKeyNames=[], filterKeyValues=[], groupKeyNames=['Recording/RecGroup'], groupKeyReadableNames=['Recording group']), 
                title='By recording group'
            )
        )

    # By channel name:
    showByChannelName = Prefs['showByChannelName']
    if showByChannelName:
        dir.add(
            DirectoryObject(
                key=Callback(GroupRecordingsBy, filterKeyNames=[], filterKeyValues=[], groupKeyNames=['Channel/ChannelName'], groupKeyReadableNames=['Channel name']), 
                title='By channel'
            )
        )

    # By recording date:
    dir.add(
        DirectoryObject(
            key=Callback(GetRecordingList, filterKeyNames=[], filterKeyValues=[], sortKeyName='StartTime'), 
            title='By recording date', 
            thumb=R(BY_DATE)
        )
    )

    # Preferences:
    dir.add(
        PrefsObject(
            title="Preferences", 
            summary="Configure how to connect to the MythTV backend", 
            thumb=R("icon-prefs.png")
        )
    )

    return dir


####################################################################################################
# GroupRecordingsBy:
# ==================
# Returns a tree-structure of all the recordings matching the specified filter.
#
# The recordings will be sorted into sub-directories according to the value of
# the group-by key. The group-by key is the first element of the groupKeyNames
# list.
#
# Each sub-directory will have an icon (thumb) or background image (art) associated 
# with it.
#
# These images will be loaded from 
#    MythRecordings.bundle/Contents/Resources/${groupKey}Icon_%{groupValue}.png 
# and 
#    MythRecordings.bundle/Contents/Resources/${groupKey}Background_%{groupValue}.png 
# respectively.
#
# Returns:
#    ObjectContainer
####################################################################################################
@route('/video/mythrecordings/GroupRecordingsBy', filterKeyNames = list, filterKeyValues = list, groupKeyNames = list, groupKeyReadableNames = list, allow_sync=True) 
def GroupRecordingsBy(groupKeyNames, groupKeyReadableNames = [], filterKeyNames = [], filterKeyValues = [], backgroundName = ''):
	if groupKeyNames is None:
		groupKeyNames = []

	if filterKeyNames is None:
		filterKeyNames = []

	if filterKeyValues is None:
		filterKeyValues = []

	if len(filterKeyValues) != len(filterKeyNames):
		raise(Exception('Code error: filter key name and value lists should be of equal length'))

	if len(groupKeyNames)==0:
		return GetRecordingList(filterKeyNames=filterKeyNames, filterKeyValues=filterKeyValues, sortKeyName='StartTime', backgroundName = backgroundName)

	keyName = groupKeyNames[0]
	del groupKeyNames[0]

	if (len(groupKeyReadableNames)>0):
		keyReadableName = groupKeyReadableNames[0]
		del groupKeyReadableNames[0]
	else:
		keyReadableName = keyName

	iconPrefix = "%sIcon_" % CamelCase(keyReadableName)
	backgroundPrefix = "%sBackground_" % CamelCase(keyReadableName)
	
	# Determine a good top-of-page title:
        title = MakeTitle(keyName, filterKeyNames, filterKeyValues)

	oc = ObjectContainer(title2=title, art=R(backgroundName)) # title1 is not displayed (on most clients, anyway)
	
	# Get the recordings metadata from the MythTV backend:
	recordings = GetMythTVRecordings(filterKeyNames, filterKeyValues)
	
	# Sort the recordings into a {string : list} dictionary
	entries = {}
	for recording in recordings:
		keyValue = GetField(recording, keyName)

		if not entries.has_key(keyValue):
			entries[keyValue] = []
		entries[keyValue].append(recording)

	# Loop through each of the keys and create a subdirectory entry:
	for subdirName in entries.keys():
		subFilterKeyNames = list(filterKeyNames)
		subFilterKeyNames.append(keyName)
		subFilterKeyValues = list(filterKeyValues)
		subFilterKeyValues.append(subdirName)

		iconName = '%s%s.png' % (iconPrefix, subdirName)
		Log('iconName = %s' % iconName)
		backgroundName = '%s%s.png' % (backgroundPrefix, subdirName)
		Log('backgroundName = %s' % backgroundName)

		subdirContents = entries[subdirName]
		entryTitle = "%s (%s)" % (subdirName, len(subdirContents))
		
		if len(subdirContents) == 1:
                        # Experimental:
                        # =============
                        # If the subdirectory we're about to create only contains a
                        # single entry, we'll save the directory and just put the
                        # recording in.
			recording = subdirContents[0]
			oc.add(Recording(recording, backgroundName))
		else:
                        # Otherwise, we'll play it straight and put in a DirectoryObject
                        # referencing the next level down
			oc.add(
                            DirectoryObject(
                                key=
                                    Callback(
                                        GroupRecordingsBy, 
                                        filterKeyNames=subFilterKeyNames, 
                                        filterKeyValues=subFilterKeyValues, 
                                        groupKeyNames=groupKeyNames,
                                        groupKeyReadableNames=groupKeyReadableNames,
                                        backgroundName=backgroundName
                                    ), 
                                title=entryTitle, 
                                thumb=R(iconName), 
                                art=R(backgroundName)
                            )
                        )
		
	oc.objects.sort(key=lambda obj: obj.title)
	return oc

def MakeTitle(groupBy, filterKeyNames, filterKeyValues):
    if len(filterKeyNames) == 0:
        title = 'By %s' % groupBy
    else:
        title = ""
        for n in range(0, len(filterKeyNames)):
            keyN = filterKeyNames[n]
            valueN = filterKeyValues[n]
            title = title + ', %s "%s"' % (keyN, valueN)
        title = title + ', by %s' % groupBy
        title = title[2:] # remove starting ", "
    return title

def CamelCase(src):
    #return ''.join(x for x in src.title() if not x.isspace())
    return src.title().replace(' ', '')


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
def GetRecordingList(filterKeyNames, filterKeyValues, sortKeyName = None, sortReverse = True, backgroundName = ''):
	url = PVR_URL + 'Dvr/GetRecordedList'
	Log('GetRecordingList(filterKeyNames="%s", filterKeyValues="%s", sortKeyName="%s"): Loading URL %s' % (filterKeyNames, filterKeyValues, sortKeyName, url))

	title2= "By title"
	if not filterKeyValues is None:
		title2 = " - ".join(filterKeyValues)

	oc = ObjectContainer(title2 = title2)

	if not backgroundName == '':
		oc.art = R(backgroundName)

	recordings = GetMythTVRecordings(filterKeyNames, filterKeyValues)
	
	if (sortKeyName is not None):
		recordings.sort(key=lambda rec: rec.find(sortKeyName).text, reverse=sortReverse)
	
	for recording in recordings:
		oc.add(Recording(recording, backgroundName))
			
	return oc



####################################################################################################
def Recording(recording, backgroundName = ''):
	
	# Mandatory properties: Title, Channel, StartTime, EndTime:
	# =========================================================
	showname = GetField(recording, 'Title') # recording.find('Title').text
	chanId = recording.find('Channel').find('ChanId').text
	programStart = GetField(recording, 'StartTime') # recording.find('StartTime').text
	programEnd = GetField(recording, 'EndTime') # recording.find('EndTime').text
	recordingStart = GetField(recording, 'Recording/StartTs') # recording.find('Recording/StartTs').text
	recordingEnd = GetField(recording, 'Recording/EndTs') # recording.find('Recording/EndTs').text

	shouldStart = datetime.datetime.strptime(programStart,"%Y-%m-%dT%H:%M:%SZ")
	didStart = datetime.datetime.strptime(recordingStart,"%Y-%m-%dT%H:%M:%SZ")
	shouldEnd = datetime.datetime.strptime(programEnd,"%Y-%m-%dT%H:%M:%SZ")
	didEnd = datetime.datetime.strptime(recordingEnd,"%Y-%m-%dT%H:%M:%SZ")

	fileName = GetField(recording, 'FileName') # recording.find('FileName').text
	storageGroup = GetField(recording, 'Recording/StorageGroup') # recording.find('Recording/StorageGroup').text

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
		#epname = recording.find('SubTitle').text
		epname = GetField(recording, 'SubTitle')
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
		descr = GetField(recording, 'Description').strip() #recording.find('Description').text.strip()
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
# RecordingInfo:
# ==============
# Returns an ObjectContainer with metadata about a recording, as required by the VideoClipObject.
# The purpose is a bit mysterious, but it's required.
#
# Return:
#    ObjectContainer
####################################################################################################
@route('/video/mythrecordings/GetRecordingInfo', allow_sync=True)
def RecordingInfo(chanId, startTime, backgroundName):
	url = PVR_URL + 'Dvr/GetRecorded?StartTime=%s&ChanId=%s' % (startTime, chanId)
	request = urllib2.Request(url, headers={"Accept" : "application/xml"})
	Log('RecordingInfo(chanId="%s", startTime="%s" backgroundName="%s"): opening %s' % (chanId, startTime, url))
	u = urllib2.urlopen(request)
	tree = ET.parse(u)
	root = tree.getroot()

	recording = root #.findall('Programs/Program')

	recording_object = Recording(recording, backgroundName)
	return ObjectContainer(objects=[recording_object], art=R(backgroundName))


####################################################################################################
# GetMythTVRecordings:
# ====================
# Gets a list of all recording structures matching the specified filters.
#
# Return:
#    list of recording (the structure of a recording is irrelevant - use GetField to
#                       retrieve the value of a field)
####################################################################################################
def GetMythTVRecordings(filterKeyNames, filterKeyValues):
	url = PVR_URL + 'Dvr/GetRecordedList'
	request = urllib2.Request(url, headers={"Accept" : "application/xml"})
	u = urllib2.urlopen(request)
	tree = ET.parse(u)
	root = tree.getroot()
	
	# Loop through recordings, filtering as specified:
	recordings = root.findall('Programs/Program')
	result = []
	for recording in recordings:
		if recording.find('Recording/RecGroup').text == 'Deleted':
			continue
		if recording.find('Recording/RecGroup').text == 'LiveTV':
			continue
		if recording.find('Title').text == 'Unknown':
			continue
		if not Match(filterKeyNames, filterKeyValues, recording):
			continue

		result.append(recording)

	return result

def Match(filterKeyNames, filterKeyValues, recording):
	for n in range(0, len(filterKeyNames)):
		filterKeyName = filterKeyNames[n]
		filterKeyValue = filterKeyValues[n]
		actualFilterKeyValue = GetField(recording, filterKeyName)
		if not actualFilterKeyValue == filterKeyValue:
			return False
	return True


####################################################################################################
# GetField:
# =========
# Gets the value of a field in the recording AFTER having performed alias substitution on it,
#
# The value thus found is passed through an aliasing mechanism, intended to conflate almost-identical
# values (like "Series" and "Serie" or "Tonight Show" and "The Tonight Show"). See the LoadAliases
# function for details.
#
# Return:
#    string
#
####################################################################################################
def GetField(recording, fieldName):
	if fieldName == "Title" or fieldName == "SubTitle":
		subtitle = recording.find('SubTitle').text
		title = recording.find('Title').text

		# If subtitle is empty, we try splitting the title:
		if subtitle is None or subtitle == "":
			for splitter in TITLE_SPLITTERS:
				splitResult = title.split(splitter, 1)
				if len(splitResult) == 2:
					orgTitle = title
					title,subtitle = splitResult
					#Log('Split title "%s" into ("%s", "%s")' % (orgTitle, title, subtitle))
					break

		if fieldName == "Title":
			return title
		if fieldName == SubTitle:
			return subtitle

	if fieldName == "Category":
		keyAliases = LoadAliases('categoryAliases')
		orgKeyValue = recording.find(fieldName).text
		return MapAliases(orgKeyValue, keyAliases)

	return recording.find(fieldName).text


####################################################################################################
# MapAlias:
# =========
# Maps a string into its canonical version (if any), using an alias list loaded by LoadAliases.
#
# Return:
#    string
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
# LoadAliases:
# ============
# Loads a list of aliases from the preferences string specified by the parameter aliasPrefName.
#
# The alias list if a JSON formatted list of list of strings. Each list-of-strings is interpreted
# as a canonical name, followed by its synonyms.
#
# Return:
#    list of list of strings
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
		#Log('keyAliasString = %s', keyAliasString)
		keyAliases = json.loads(keyAliasString)
		#Log('keyAliases = %s', keyAliases)
	except:
		keyAliases = [] # no aliases, then

	return keyAliases


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
