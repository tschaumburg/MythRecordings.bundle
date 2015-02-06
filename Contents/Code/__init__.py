# MythRecordings plug-in for Plex
# Copyright (C) 2013 Thomas Schaumburg
#
# This code is heavily inspired by the NextPVR bundle by David Cole.

import xml.etree.ElementTree as ET
import datetime
import urllib2
import json
import re
import cgi

def L2(key):
	result = str(L(key))
	return result

def F2(key, *args):
	return str(F(key, *args))

####################################################################################################
NAME = "PLUGIN_TITLE"
PVR_URL = 'http://%s:%s/' % (Prefs['server'],Prefs['port'])
CACHE_TIME = int(Prefs['cacheTime'])
DETECT_SERIES_BY_TITLE = True #bool(Prefs['detectSeriesByTitle'])

MYTHTV_BACKGROUND = 'mythtv-background.png'
MYTHTV_ICON = 'mythtv-icon.png'

BY_NAME_ICON  = 'by-name-icon.png'
BY_NAME_BACKGROUND  = 'by-name-background.png' # TODO: missing

BY_DATE_ICON  = 'by-date-icon.png'
BY_DATE_BACKGROUND  = 'by-date-background.png' # TODO: missing

BY_CATEGORY_ICON  = 'by-category-icon.png'
BY_CATEGORY_BACKGROUND  = 'by-category-background.png' # TODO: missing

UNKNOWN_SERIES_BACKGROUND = 'unknown-series-background.png' # TODO: missing
UNKNOWN_SERIES_ICON = 'unknown-series-icon.png' # TODO: missing

SCREENSHOT_ICON_HEIGHT = None
SCREENSHOT_ICON_WIDTH = 128

####################################################################################################
# Developer configurable data:
# ============================
# This section contains configuration that you only need to change if you change the code.
####################################################################################################

# ReadableKeyNames:
# =================
# Key names are XPATH expressions that are used to retrieve values (title, recording start time,
# etc.) from the XML metadata describing a recording.
#
# Sometimes, a screen needs to display the key used to organize data (such as a label saying
# "sort by xxx".
#
# In these cases, we need a simple way of getting a human-readable form of a key (after all,
# "sort by Recording/RecGroup" doesn't sound very approachable...)
#
# So: whenever you add a literal XPATH expression in a call to GroupRecordingsBy, you may
# want to add a human-readableform to the dictionary below.

ReadableKeyNames = \
    {
        "Recording/RecGroup": "RECORDING GROUP",
        "Channel/ChannelName": "CHANNEL NAME",
        "StartTime": "RECORDING DATE",
	"Category": "CATEGORY",
	"Title" : "TITLE"
    }

def GetReadableKeyName(keyname):
    if keyname in ReadableKeyNames.keys():
        return ReadableKeyNames[keyname]
    else:
        return keyname

####################################################################################################
# User configurable data:
# =======================
# This section contains configuration that a user may wish to configure according to taste and 
# needs.
# 
# This really belongs in the user preferences. But since preferences only handle simple types
# (bool, text,...), this proved unwieldy (editing a Python list-of-lists using a 4-button Roku
# remote control is ... interesting).
#
# So for now, these settings go in here. If you have a better idea, let me know.
####################################################################################################

# Title splitting
# ===============
# Sometimes the episodes of a series will include the subtitle in the title, which means that
# the episodes cannot be properly combined by title.
#
# For example, I may have recorded two episodes of the 2012 "Sherlock Holmes" season, with the
# following metadata:
#
#    {Title = "Sherlock Holmes - A Scandal in Belgravia", Subtitle = "British series, 2012"}
#    {Title = "Sherlock Holmes - The Hounds of Baskerville", Subtitle = "British series, 2012"}
#
# These do not match by title, and will not immediately be recognized as episodes of the same 
# series.
#
# But if you add "-" to the title splitters list below, the metadata will be reorganized as 
# follows:
#
#    {Title = "Sherlock Holmes", Subtitle = "A Scandal in Belgravia - British series, 2012"}
#    {Title = "Sherlock Holmes", Subtitle = "The Hounds of Baskerville - British series, 2012"}
#
# Example TitleSplitters.json:
#    [
# 	   '-', 
# 	   ':'
#    ]
#
# However, there are titles that SHOULD contain a splitter (such as "CSI: New York"). These
# titles are protected by adding a regular expression to the TITLE_NOSPLITTERS collection.
# Titles that match one of these regexps are exempt from title splitting.
#
# Example TitleSplitExemptions.json:
#    [
# 	   "^CSI: New York"
#    ]

TITLE_SPLITTERS = json.loads(Resource.Load("TitleSplitters.json"))
TITLE_NOSPLITTERS = json.loads(Resource.Load("TitleSplitExemptions.json")) # Regular expression matching

# Category aliases
# ================
# When grouping recordings by category, the category names are not always consistent -
# often the category values deoend on the channel the recording was made from.
# 
# To avoid having the category list filled up with categories that only vary in spelling
# or language, the CategoryAliases list-of-lists below is used.
# 
# CategoryAliases is a list of alias lists. Each alias list consists of the canonical 
# name, followed by aliases.
#
# Whenever an alias value is met, it is replaced with the corresponding canonical name.
# 
# Example CategoryAliases.json:

# 	[
# 		["SERIES", "Series", "series", "serie"],
# 		["CHILDREN", "Children", "kids"], 
# 		["DOCUMENTARY", "documentary", "educational"], 
# 		["ENTERTAINMENT", "Entertainment", "entertainment"], 
# 		["MOVIES", "Movie", "movie", "film", "Film", "drama", "Drama"], 
# 		["SPORT", "Sport", "sport", "Football", "football", "Fodbold", "fodbold"], 
# 		["UNCATEGORIZED", "Uncategorized", "", "Ukategoriseret"]
# 	]

CategoryAliases = json.loads(Resource.Load("CategoryAliases.json"))

####################################################################################################

def Start():
    	
	ObjectContainer.title1 = L2(NAME)
	Log('%s Started' % L2(NAME))
	Log('Base URL set to %s' % PVR_URL)

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
    dir=ObjectContainer(art = R(MYTHTV_BACKGROUND))

    # By title:
    dir.add(
        DirectoryObject(
            key=Callback(GroupRecordingsBy, groupByList=['Title'], staticBackground=BY_NAME_BACKGROUND), 
            title=L2('BY_TITLE'), 
            thumb=R(BY_NAME_ICON)
        )
    )
    
    # By category, then by title:
    dir.add(
        DirectoryObject(
            key=Callback(GroupRecordingsBy, groupByList=['Category', 'Title'], staticBackground=BY_CATEGORY_BACKGROUND), 
            title=L2('BY_CATEGORY'), 
            thumb=R(BY_CATEGORY_ICON)
        )
    )

    # By recording group:
    showByRecordingGroup = Prefs['showByRecordingGroup']
    if showByRecordingGroup:
        dir.add(
            DirectoryObject(
                key=Callback(GroupRecordingsBy, groupByList=['Recording/RecGroup']), 
                title=L2('BY_RECORDING_GROUP')
            )
        )

    # By channel name:
    showByChannelName = Prefs['showByChannelName']
    if showByChannelName:
        dir.add(
            DirectoryObject(
                key=Callback(GroupRecordingsBy, groupByList=['Channel/ChannelName']), 
                title=L2('BY_CHANNEL')
            )
        )

    # By recording date:
    dir.add(
        DirectoryObject(
            key=Callback(GetRecordingList, sortKeyName='StartTime', staticBackground=BY_DATE_BACKGROUND), 
            title=L2('BY_RECORDING_DATE'), 
            thumb=R(BY_DATE_ICON)
        )
    )

    # Preferences:
    dir.add(
        PrefsObject(
            title=L2("PREFERENCES"), 
            summary=L2("PREFERENCES_SUMMARY"), 
            thumb=R("icon-prefs.png")
        )
    )

    return dir


####################################################################################################
# GroupRecordingsBy:
# ==================
# Returns a tree-structure of all the recordings matching the specified filter.
#
# The recordings will be grouped into sub-directories according to the value of
# the group-by key. The group-by key is the first element of the groupBy
# list.
#
# Each sub-directory will have an icon (thumb) and background image (art) associated 
# with it.
#
# These images will be loaded from 
#    MythRecordings.bundle/Contents/Resources/${groupKey}Icon_%{groupValue}.png 
# and 
#    MythRecordings.bundle/Contents/Resources/${groupKey}Background_%{groupValue}.png 
# respectively.
#
#
# Parameters:
# -----------
#    groupByList:      A string list of the keys to group each level of the tree by.
#    filterBy:         A string:string dictionary af (name, value) pairs. Only recordings
#                      matching this filter are listed in the tree-structure returned.
#    seriesInetRef:    If set, it indicates that MythTV has identified the recordings
#                      matching the filter as episodes of a series. The value of
#                      seriesInetRef can be used to retrieve metadata from the MythTV
#                      server.
#    staticBackground: The resource name of an image to use as background art for
#                      this level.
#
# Returns:
# --------
#    ObjectContainer
#
#
# Experimental series handling:
# ------------------------------
# In case the group-by key is "Title", the set of recordings for each value of title
# will be searched for the "inetref" key, indicating that this is the episode of
# a series.
#
# If inetref exists, the icon and background images for that series will be retrieved
# from the MythTV server
#
####################################################################################################
@route('/video/mythrecordings/GroupRecordingsBy', filterBy = dict, groupByList = list, allow_sync=True) 
def GroupRecordingsBy(groupByList = [], filterBy = {}, seriesInetRef = None, staticBackground = None):
	Log("GroupRecordingsBy(groupByList = %s, filterBy = %s, seriesInetRef = %s, staticBackground = %s)" % (groupByList, filterBy, seriesInetRef, staticBackground))
	if groupByList is None:
		groupByList = []

	if filterBy is None:
		filterBy = {}

	# If we're not grouping, it's just a plain list (newest first seems convenient):
	if len(groupByList)==0:
		return GetRecordingList(filterBy=filterBy, sortKeyName='StartTime', seriesInetRef = seriesInetRef, staticBackground = staticBackground)
	
	# Get the key to group this level by:
	groupByKey = groupByList.pop(0)
	#groupByKey = groupByList[0]
	#del groupByList[0]

	# Determine a good top-of-page title:
        title = MakeTitle(filterBy, groupByKey)

	# Find a background image:
	if seriesInetRef is None:
		backgroundUrl = R(staticBackground)
	else:
		backgroundUrl = GetSeriesBackground(seriesInetRef, staticBackground)

	oc = ObjectContainer(title2=title, art=backgroundUrl) # title1 is not displayed (on most clients, anyway)
	
	# Get the recordings metadata from the MythTV backend:
	recordings = GetMythTVRecordings(filterBy)
	
	# Sort the recordings into a {string : recording[]} dictionary
	entries = {}
	for recording in recordings:
		keyValue = GetField(recording, groupByKey)

		if not entries.has_key(keyValue):
			entries[keyValue] = []
		entries[keyValue].append(recording)

	# Loop through the keys and create a subdirectory entry for each:
	for subdirName in entries.keys():
		# make sure that only the matching recordings appear in the subdir:
                subdirFilterBy = filterBy.copy()
                subdirFilterBy[groupByKey] = subdirName

		subdirContents = entries[subdirName]
		entryTitle = "%s (%s)" % (L2(subdirName), len(subdirContents))
		
		# Icon and background image for the subdir:
		subSeriesInetRef = None
		subdirIconUrl = None
		subdirStaticBackground = None
		if groupByKey == "Title":
			if not DETECT_SERIES_BY_TITLE:
				# If we're grouping by title, we have no way of
				# getting a proper icon/background.
				subdirIconUrl = R(UNKNOWN_SERIES_ICON)
				subdirStaticBackground = UNKNOWN_SERIES_BACKGROUND
			else:
				# Experimental: we're assuming that recordings with the same
				# name are episode of a series.
				subSeriesInetRef = GetInetref(subdirContents)
				subdirIconUrl = GetSeriesIcon(subSeriesInetRef, UNKNOWN_SERIES_ICON)
				subdirStaticBackground = UNKNOWN_SERIES_BACKGROUND
		else:
			# If we're grouping by anything-but title, we'll look
			# for static resources:
			subdirIconUrl = R('%sIcon_%s.png' % (CamelCase(GetReadableKeyName(groupByKey)), CamelCase(subdirName)))
			subdirStaticBackground = '%sBackground_%s.png' % (CamelCase(GetReadableKeyName(groupByKey)), CamelCase(subdirName))

		# Create the subdir:
		if len(subdirContents) == 1 and groupByKey == "Title": 
                        # Experimental:
                        # =============
                        # If the subdirectory we're about to create only contains a
                        # single entry, we'll save the extra level and just put the
                        # recording in.
			recording = subdirContents[0]
			oc.add(Recording(recording, seriesInetRef=subSeriesInetRef))
		else:
                        # Otherwise, we'll play it straight and recurse the next level down
			oc.add(
                            DirectoryObject(
                                key=
                                    Callback(
                                        GroupRecordingsBy,
                                        filterBy=subdirFilterBy,
                                        groupByList=groupByList,
                                        seriesInetRef=subSeriesInetRef,
					staticBackground = subdirStaticBackground
                                    ), 
                                title=entryTitle.decode(), 
                                thumb=subdirIconUrl
                            )
                        )
		
	oc.objects.sort(key=lambda obj: obj.title)
	return oc

####################################################################################################
# Series meta-data:
# =================
# Get metadata about a series, as recorded by MythTV
####################################################################################################

def GetInetref(recordings):
	for recording in recordings:
		val = GetField(recording, 'Inetref')
		if not val is None:
			return val
	return None

def GetSeriesIcon(inetref, staticBackground = UNKNOWN_SERIES_ICON):
	url = "%sContent/GetRecordingArtwork?Inetref=%s&Type=fanart" % (PVR_URL, inetref)
	if SCREENSHOT_ICON_HEIGHT:
		url = url + "&Height=%s" % SCREENSHOT_ICON_HEIGHT
	if SCREENSHOT_ICON_WIDTH:
		url = url + "&Width=%s" % SCREENSHOT_ICON_WIDTH
	return Resource.ContentsOfURLWithFallback(url = url, fallback = staticBackground)

def GetSeriesBackground(inetref, staticBackground = UNKNOWN_SERIES_BACKGROUND):
	url = "%sContent/GetRecordingArtwork?Inetref=%s&Type=fanart" % (PVR_URL, inetref)
	return Resource.ContentsOfURLWithFallback(url = url, fallback = staticBackground)


#return cgi.escape(str, quote=True).encode('ascii', 'xmlcharrefreplace')

####################################################################################################
# Title handling:
# ===============
####################################################################################################

def MakeTitle(filterBy, groupByKey):
    readableGroupByKey = L2(GetReadableKeyName(groupByKey))
    if len(filterBy) == 0:
        title = F2("BY1", first_lower(readableGroupByKey))
    else:
        title = ""
        for filterKeyName, filterKeyNameValue in filterBy.items():
            readableFilterKeyName = L2(GetReadableKeyName(filterKeyName))
            title = title + ', %s "%s"' % (readableFilterKeyName, L2(filterKeyNameValue))
        title = title + ', ' + F2("BY2", first_lower(readableGroupByKey))
        title = title[2:] # remove starting ", "
    return str(title) #.replace('æ', 'a')

def CamelCase(src):
    result = re.sub(r'\W+', '', src.title())
    return result

def first_lower(s):
   if len(s) == 0:
      return s
   else:
      return s[0].lower() + s[1:]

####################################################################################################
# GetRecordingList:
# =================
# Creates a directory (ObjectContainer) listing all the recordings where the contents of the element
# identified by the filterKeyNames parameter (a lis of XPATH expressions) matches filterKeyValues. The
# values are subject to the same aliasing mechanism described for GroupRecordingsBy above.
#
# Each entry in the recording list will have an icon (thumb) that is a Preview Image from the recording,
# as supplied by MythTV.
#
# The resulting list of recordings is sorted by the element identified by the sortKeyName parameter
# (another XPATH expression)
####################################################################################################
@route('/video/mythrecordings/GetRecordingList', filterBy = dict, allow_sync=True)
def GetRecordingList(filterBy = {}, sortKeyName = None, sortReverse = True, seriesInetRef = None, staticBackground = None):
	Log("GetRecordingList(filterBy = %s, sortKeyName = %s, sortReverse = %s, seriesInetRef = %s, staticBackground = %s)" % (filterBy, sortKeyName, sortReverse, seriesInetRef, staticBackground))

	backgroundUrl = GetSeriesBackground(seriesInetRef, staticBackground)
	oc = ObjectContainer(
		title2 = MakeTitle(filterBy, sortKeyName), 
		art = backgroundUrl
	)
	
	recordings = GetMythTVRecordings(filterBy)

	# Sorting the list:
	if (sortKeyName is not None):
		recordings.sort(key=lambda rec: rec.find(sortKeyName).text, reverse=sortReverse)
	
	for recording in recordings:
		recordingEntry = Recording(recording, seriesInetRef = seriesInetRef)
		oc.add(recordingEntry)
			
	return oc

def all_same(items):
	if len(items) == 0:
		return True
	first =items[0]
	for item in items:
		if not item == first:
			return False
	return True

####################################################################################################
def Recording(recording, seriesInetRef = None, staticBackground = None):
	Log("Recording(recording = %s, seriesInetRef = %s, staticBackground = %s)" % (identify_recording(recording), seriesInetRef, staticBackground))
	
	# Mandatory properties: Title, Channel, StartTime, EndTime:
	# =========================================================
	showname = GetField(recording, 'Title')
	chanId = GetField(recording, 'Channel/ChanId')
	programStart = GetField(recording, 'StartTime')
	programEnd = GetField(recording, 'EndTime')
	recordingStart = GetField(recording, 'Recording/StartTs')
	recordingEnd = GetField(recording, 'Recording/EndTs')

	shouldStart = datetime.datetime.strptime(programStart,"%Y-%m-%dT%H:%M:%SZ")
	didStart = datetime.datetime.strptime(recordingStart,"%Y-%m-%dT%H:%M:%SZ")
	shouldEnd = datetime.datetime.strptime(programEnd,"%Y-%m-%dT%H:%M:%SZ")
	didEnd = datetime.datetime.strptime(recordingEnd,"%Y-%m-%dT%H:%M:%SZ")

	fileName = GetField(recording, 'FileName')
	storageGroup = GetField(recording, 'Recording/StorageGroup')

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
		playbackURL = PVR_URL + 'Content/GetFile?StorageGroup=%s&FileName=%s' % (storageGroup,fileName,)
	else:
		playbackURL = PVR_URL + 'Content/GetRecording?ChanId=%s&StartTime=%s' % (chanId,recordingStart,)

	# Optional properties:
	# ====================	

	
	# SubTitle:
	# =========

	try:
		epname = GetField(recording, 'SubTitle')
		epname = "%s (%s)" % (epname, shouldStart.strftime('%Y-%m-%d'))
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

		warning = ""
		if (missedStart and missedEnd):
			warning = F2("ERROR_MISSED_BOTH", str(missedAtStart),str(missedAtEnd)) + "\n"
		elif (missedStart):
			warning = F2("ERROR_MISSED_START", str(missedAtStart)) + "\n"
		elif (missedEnd):
			warning = F2("ERROR_MISSED_END", str(missedAtEnd)) + "\n"
		else:
			warning = ""

		if stillRecording:
			warning = L2("STATUS_STILL_RECORDING") + '\n' + warning

	except:

		Warning('Recording: Recording: "%s", Duration error, Unexpected error' % showname)
		
	# Description:
	# ============
	try:
		descr = GetField(recording, 'Description').strip() 
		if descr is None:
			descr = ""
	except:
		Warning('Recording: Recording: "%s", Descr error, Unexpected error' % showname)
		descr = ""


	# ChanId:
	# =======
	try:
		channel = GetField(recording, 'Channel/ChanId')
		if channel == '0':
			channel = None
	except:
		Warning('Recording: Recording: "%s", Could not get channel ID' % showname)			
		channel = None

	
	# Title + subtitle:
	# =================
	maxlength = 120
	if len(showname) + len(epname) + 3 < maxlength:
		header = showname + " - " + epname
		tagline = None
	else:
		header = showname
		tagline = epname

	if len(header) > maxlength:
		header = header[:maxlength] + "..."

	if stillRecording:
		header = header + " (" + L2("STATUS_STILL_RECORDING_2") + ")"


	# Screenshot:
	# ===========
	if not channel is None and not recordingStart is None:
		screenshotUrl = PVR_URL + '/Content/GetPreviewImage?ChanId=%s&StartTime=%s' % (channel, recordingStart)
		if SCREENSHOT_ICON_HEIGHT:
			screenshotUrl = screenshotUrl + "&Height=%s" % SCREENSHOT_ICON_HEIGHT
		if SCREENSHOT_ICON_WIDTH:
			screenshotUrl = screenshotUrl + "&Width=%s" % SCREENSHOT_ICON_WIDTH
		thumb = Resource.ContentsOfURLWithFallback(url = screenshotUrl, fallback = UNKNOWN_SERIES_BACKGROUND)
		backgroundUrl = Resource.ContentsOfURLWithFallback(url = screenshotUrl, fallback = UNKNOWN_SERIES_BACKGROUND)
	else:
		thumb = R(MYTHTV_ICON)
		backgroundUrl = R(MYTHTV_BACKGROUND)

	return VideoClipObject(
                title = header,
		tagline = tagline,
                summary = warning + descr,
                originally_available_at = shouldStart,
                thumb = thumb,
		art = backgroundUrl,
		duration = int(duration),
		key = Callback(RecordingInfo, chanId=chanId, startTime=recordingStart, seriesInetRef=seriesInetRef),
		rating_key= str(int(shouldStart.strftime('%Y%m%d%H%M'))),
		items = [
			MediaObject(
				parts = [
					PartObject(key=playbackURL, duration=int(duration))
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
def RecordingInfo(chanId, startTime, seriesInetRef = None):
	Log('RecordingInfo(chanId="%s", startTime="%s" seriesInetRef="%s")' % (chanId, startTime, seriesInetRef))
	url = PVR_URL + 'Dvr/GetRecorded?StartTime=%s&ChanId=%s' % (startTime, chanId)
	request = urllib2.Request(url, headers={"Accept" : "application/xml"})
	u = urllib2.urlopen(request)
	tree = ET.parse(u)
	root = tree.getroot()

	recording = root #.findall('Programs/Program')

	# Background image:
	# =================
	backgroundUrl = GetSeriesBackground(seriesInetRef, None)

	recording_object = Recording(recording, seriesInetRef)
	return ObjectContainer(objects=[recording_object], art=backgroundUrl)


####################################################################################################
# GetMythTVRecordings:
# ====================
# Gets a list of all recording structures matching the specified filters.
#
# Return:
#    list of recording (the structure of a recording is irrelevant - use GetField to
#                       retrieve the value of a field)
####################################################################################################
def GetMythTVRecordings(filterBy, maxCount=None):
	root = InternalGetRecordedList(maxCount)
	
	# Loop through recordings, filtering as specified:
	recordings = root.findall('Programs/Program')
	result = []
	for recording in recordings:
		if recording.find('Recording/RecGroup').text == 'Deleted':
			continue
		if recording.find('Recording/RecGroup').text == 'LiveTV':
			continue
		if recording.find('FileSize').text == '0':
			continue
		if recording.find('Title').text == 'Unknown':
			continue
		if not Match(filterBy, recording):
			continue

		result.append(recording)

	return result

def InternalGetRecordedList(maxCount=None):
	url = PVR_URL + 'Dvr/GetRecordedList'
	if not maxCount is None:
		url = url + "?Count=" + str(maxCount)
	xmlstring = HTTP.Request(url, cacheTime = CACHE_TIME).content
	root = ET.fromstring(xmlstring)
	
	return root

def Match(filterBy, recording):
	for filterKeyName, filterKeyValue in filterBy.items():
		actualFilterKeyValue = GetField(recording, filterKeyName)
		if not actualFilterKeyValue == filterKeyValue:
			return False
	return True

def identify_recording(recording):
	if recording is None:
		return "None"
	chanId = GetField(recording, 'Channel/ChanId')
	programStart = GetField(recording, 'Recording/StartTs')
	return "%s/%s" % (chanId, programStart)
	
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
		if not subtitle is None:
			subtitle = subtitle.decode()

		title = recording.find('Title').text
		if not title is None:
			title = title.decode()
		
		dontSplit = False
		for nosplitter in TITLE_NOSPLITTERS:
			dontSplit = re.search(nosplitter, title)
			if dontSplit:
				break

		if not dontSplit:
			for splitter in TITLE_SPLITTERS:
				splitResult = title.split(splitter, 1)
				if len(splitResult) == 2:
					orgTitle = title
					title,newsubtitle = splitResult
					title = title.strip()
					newsubtitle = newsubtitle.strip()
					if subtitle:
						subtitle = newsubtitle# + " - " + subtitle
					break

		if fieldName == "Title":
			return title
		if fieldName == 'SubTitle':
			return subtitle

	if fieldName == "Category":
		keyAliases = LoadAliases('categoryAliases')
		orgKeyValue = recording.find(fieldName).text
		if not orgKeyValue is None:
			orgKeyValue = orgKeyValue.decode()
		return MapAliases(orgKeyValue, keyAliases)

	result = recording.find(fieldName).text
	if not result is None:
		result = result.decode()

	return result


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
	
	if isinstance(keyAliases, list): 
		for aliasList in keyAliases:
			if (keyValue in aliasList):
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

	# Workaround:
	# =========== 
	# It is really difficult to edit a list-of-lists in the preferences editor
	# - so we're moving the aliases to hardcoded variables for now:
	if aliasPrefName == "categoryAliases":
		return CategoryAliases

	return []

#####################################################################################################
def ValidatePrefs():
	global PVR_URL
	if Prefs['server'] is None:
		return MessageContainer("Error", L2("ERROR_MISSING_SERVER_INFO"))
	elif Prefs['port'] is None:
		return MessageContainer("Error", L2("ERROR_MISSING_SERVER_PORT"))
	elif not Prefs['port'].isdigit():
		return MessageContainer("Error", L2("ERROR_SERVER_PORT_NON_NUMERIC"))
	else:
		port = Prefs['port']
		PVR_URL = 'http://%s:%s/' % (Prefs['server'], port)
		Log('ValidatePrefs: PVR URL = %s' % PVR_URL)
		try:
			testXML = InternalGetRecordedList(1)
			Log("ValidatePrefs succeeded")

			# Should we test the 
			#    <Version>0.25.20110928-1</Version>
			# element for ver >= 0.27
			version = testXML.find('Version').text
			major, minor, rest = version.split('.', 2)
			major = int(major)
			minor = int(minor)
		except:
			Log("ValidatePrefs failed")
			return MessageContainer("Error", F2("MYTHSERVER_UNAVAILABLE", Prefs['server'], port))

		if major >= 0 and minor >=27:
			return MessageContainer("Success","Your MythTV server is version %s" % version)
		else:
			return MessageContainer("Warning","Your MythTV server is version %s - this plugin is developed for version 0.27 and later" % version)

