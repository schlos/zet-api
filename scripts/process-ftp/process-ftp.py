from ftplib import FTP
from datetime import datetime, timedelta
from HRTBus import Checkin
from HRTDatabase import HRTDatabase
import config

def checkinProcessed(checkin):
    if lastCheckins is None:
        return False
    if checkin.time == lastCheckins["time"]:
        return checkin.busId in lastCheckins["busIds"]
    return checkin.time < lastCheckins["time"]

def process(text):
    global lastRepeat
    
    if not text.strip():
        return
    
    stats['lines'] += 1
    
    try:
        checkin = Checkin(text, str(curTime.year))
    except ValueError:
        stats['invalid'] += 1
        return
            
    if checkinProcessed(checkin):
        lastRepeat = checkin.time
        return
    
    stats['processed'] += 1
    
    if hasattr(checkin, 'routeId'):
        checkin.tripId = None
        checkin.blockId = None
        checkin.lastStopSequence = None
        checkin.lastStopSequenceOBA = None
        if hasattr(checkin, 'adherence'):
            scheduledStop = db.getScheduledStop(checkin)
            if scheduledStop is not None:
                stats['foundTrip'] += 1
                checkin.tripId = scheduledStop['trip_id']
                checkin.blockId = scheduledStop['block_id']
                checkin.lastStopSequence = scheduledStop['stop_sequence']
                checkin.lastStopSequenceOBA = scheduledStop['stop_sequence_OBA']
                checkin.scheduleMatch = True
        if checkin.tripId is None and checkin.busId in busRouteMappings:
            checkin.tripId = busRouteMappings[checkin.busId]['tripId']
            checkin.blockId = busRouteMappings[checkin.busId]['blockId']
            checkin.lastStopSequence = busRouteMappings[checkin.busId]['lastStopSequence']
            checkin.lastStopSequenceOBA = busRouteMappings[checkin.busId]['lastStopSequenceOBA']
        busRouteMappings[checkin.busId] = { 'busId': checkin.busId,
                                            'routeId' : checkin.routeId,
                                            'direction': checkin.direction, 
                                            'tripId': checkin.tripId, 
                                            'blockId': checkin.blockId,
                                            'lastStopSequence': checkin.lastStopSequence,
                                            'lastStopSequenceOBA': checkin.lastStopSequenceOBA,
                                            'time': checkin.time }
        stats['hadRoute'] += 1
    elif checkin.busId in busRouteMappings:
        checkin.routeId = busRouteMappings[checkin.busId]['routeId']
        checkin.direction = busRouteMappings[checkin.busId]['direction']
        checkin.tripId = busRouteMappings[checkin.busId]['tripId']
        checkin.blockId = busRouteMappings[checkin.busId]['blockId']
        checkin.lastStopSequence = busRouteMappings[checkin.busId]['lastStopSequence']
        checkin.lastStopSequenceOBA = busRouteMappings[checkin.busId]['lastStopSequenceOBA']
        stats['foundRoute'] += 1
    
    if hasattr(checkin, 'adherence') and hasattr(checkin, 'blockId'):
        stats['arriveTimesUpdated'] += db.updateRealTimeArrival(checkin)
    
    checkinDocs.append(checkin.__dict__)

startTime = datetime.now()

c = config.load()
db = HRTDatabase(c["db_uri"], c["db_name"])
curTime = datetime.utcnow() + timedelta(hours=-5)

busRouteMappings = db.getBusRouteMappings()
print "Read {0} Bus Route Mappings".format(len(busRouteMappings))

lastRepeat = None
lastCheckins = db.getLastCheckinSummary()
checkinDocs = []
stats = {'lines': 0, 'invalid': 0, 'processed': 0, 'hadRoute': 0, 'foundRoute': 0, 'foundTrip': 0, 'arriveTimesUpdated': 0}

ftp = FTP('216.54.15.3')
ftp.login()
ftp.cwd('Anrd')
ftp.retrlines('RETR hrtrtf.txt', process)

if lastCheckins is not None:
    print "Latest Checkin Time From Previous Run: {0}".format(lastCheckins["time"])
print "Latest Previously Processed Checkin Time From This Run: {0}".format(lastRepeat)

db.setBusRouteMappings(busRouteMappings.values())
print "Inserted {0} Bus Route Mappings".format(len(busRouteMappings))

db.updateCheckins(checkinDocs)
print "Added {0} Checkins".format(len(checkinDocs))

for key, value in stats.iteritems():
    print "{0} {1}".format(key, value)

print("Run time: " + str(datetime.now() - startTime))
