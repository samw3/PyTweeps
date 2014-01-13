# PyTweeps: Simple Python program to help manage your twitter followers.
# https://github.com/samw3/PyTweeps

import pkg_resources
import tweepy
import webbrowser
import shelve
import pprint
import sys
import traceback
import time
from datetime import datetime
from datetime import timedelta
from config import *


def isInt(s):
    try:
        int(s)
        return True
    except ValueError:
        return False


def initData(data):
    # Set up the data shelf
    if 'following' not in data.keys():
        data['following'] = set()
        data.sync()
    if 'wasFollowing' not in data.keys():
        data['wasFollowing'] = set()
        data.sync()
    if 'followers' not in data.keys():
        data['followers'] = set()
        data.sync()
    if 'wasFollowedBy' not in data.keys():
        data['wasFollowedBy'] = set()
        data.sync()
    if 'lastTweet' not in data.keys():
        data['lastTweet'] = dict()
        data.sync()


def authenticate(auth, data):
    try:
        redirect_url = auth.get_authorization_url()
        webbrowser.open(redirect_url)
        verifier = raw_input('Verifier:')
        auth.set_request_token(auth.request_token.key, auth.request_token.secret)
        try:
            auth.get_access_token(verifier)
            data['access_token_key'] = auth.access_token.key
            data['access_token_secret'] = auth.access_token.secret
            data.sync()
            auth.set_access_token(data['access_token_key'], data['access_token_secret'])

        except tweepy.TweepError:
            print 'Error! Failed to get access token.'
    except tweepy.TweepError:
        print 'Error! Failed to get request token.'


def usageMessage():
    print "Usage: python", sys.argv[0], "command [params]\n"
    print "Commands:"
    print "    update"
    print "        Updates your list of followers and followed"
    print "    bury daysSinceLastTweet numberToBury"
    print "        Remove any 'dead' tweeps. i.e. followers who no longer use twitter"
    print "    shotgun user numFollowers "
    print "        Add numFollowers followers from a user. Users no longer following and followed by are skipped"
    print "    ignore user"
    print "        Ignore a particular user, never try to follow them and unfollow if we are following."
    print ""


def error(message):
    usageMessage()
    print "ERROR: %s\n" % message
    sys.exit(-1)


def info(message):
    print message


def update(api, data):
    newUsers = 0
    totalUsers = 0
    stillFollowing = set()
    for id in api.friends_ids():
        stillFollowing.add(id)
        if id not in data['following']:
            newUsers += 1
        totalUsers += 1
    data['wasFollowing'] |= data['following']
    data['wasFollowing'] |= stillFollowing
    removed = len(data['following'] - stillFollowing)
    data['following'] = stillFollowing
    noLongerFollowing = data['wasFollowing'] - stillFollowing

    data.sync()
    print "Following %d, new %d, removed %d" % (totalUsers, newUsers, removed)

    newUsers = 0
    totalUsers = 0
    stillFollowedBy = set()
    for id in api.followers_ids():
        stillFollowedBy.add(id)
        if id not in data['followers']:
            newUsers += 1
        totalUsers += 1
    data['wasFollowedBy'] |= data['followers']
    data['wasFollowedBy'] |= stillFollowedBy
    removed = len(data['followers'] - stillFollowedBy)
    data['followers'] = stillFollowedBy
    noLongerFollowedBy = data['wasFollowedBy'] - stillFollowedBy
    data.sync()
    print "Followers %d, new %d, removed %d" % (totalUsers, newUsers, removed)
    print "No Longer Following %d" % len(noLongerFollowing)
    print "No Longer Followed by %d" % len(noLongerFollowedBy)


def main(argv):
    pp = pprint.PrettyPrinter(indent=4)

    print "\nPyTweeps v0.1 - using tweepy v%s\n" % pkg_resources.get_distribution('tweepy').version

    if len(argv) == 0:
        usageMessage()
        sys.exit(-1)

    data = shelve.open('pytweeps', writeback=True)
    initData(data)

    auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
    if 'access_token_key' not in data:
        authenticate(auth, data)
    auth.set_access_token(data['access_token_key'], data['access_token_secret'])

    api = tweepy.API(auth)

    command = argv[0]
    if command == "update":
        update(api, data)

    elif command == "bury":
        # Check params
        if len(argv) < 3:
            error("Missing params daysSinceLastTweet or numberToBury")
        if not isInt(argv[1]):
            error("daysSinceLastTweet is not an integer")
        daysSinceLastTweet = int(argv[1])
        if not isInt(argv[2]):
            error("numberToBury is not an integer")
        numberToBury = int(argv[2])
        delay = 0
        if len(argv) >= 4 and isInt(argv[3]):
            delay = argv[3]

        # death date is the cut off. if they haven't tweeted since then, bury them
        deathDate = datetime.now() - timedelta(days=daysSinceLastTweet)

        # Check the lastTweet cache, if their last tweet isn't after the deathDate don't bother checking against twitter
        last = data['lastTweet']
        lastKeys = last.keys()
        toScan = set()
        for f in data['following']:
            if f in lastKeys:
                if last[f] < deathDate:
                    toScan.add(f)
                    # else don't bother checking
            else:
                # not in cache, so check
                toScan.add(f)

        x = 0
        numBuried = 0
        try:
            for f in toScan:
                tweets = api.user_timeline(f, count=1)
                if len(tweets) == 0:
                    # Never tweeted? bury.
                    user = api.get_user(f)
                    if user.screen_name not in neverBury:
                        api.destroy_friendship(f)
                        print ""
                        info("Buried '%s' R.I.P. (No Tweets)" % user.screen_name)
                        numBuried += 1
                else:
                    lastTweet = tweets[0]
                    if (lastTweet.created_at < deathDate):
                        if lastTweet.user.screen_name not in neverBury:
                            api.destroy_friendship(f)
                            print ""
                            info("Buried '%s' R.I.P. (Last: %s)" % (
                                lastTweet.user.screen_name, unicode(lastTweet.created_at)))
                            numBuried += 1
                    else:
                        data['lastTweet'][f] = lastTweet.created_at
                        data.sync()

                if numBuried == numberToBury:
                    break

                sys.stdout.write('.')
                x += 1
                if x % 100 == 0:
                    sys.stdout.write("[" + str(x) + "]")
                sys.stdout.flush()
                if delay > 0:
                    time.sleep(float(delay))
        except tweepy.error.TweepError, e:
            print ""
            if e.message[0]['message'] == u'Rate limit exceeded':
                info("Rate limit exceeded")
            else:
                print traceback.format_exc()
                raise e
        print ""
        update(api, data)

    elif command == "shotgun":
        if len(argv) != 3:
            error("Missing params shotgun user or numFollowers")
        shotgunUser = argv[1]
        if not isInt(argv[2]):
            error("numFollowers is not an integer")
        numFollowers = int(argv[2])
        info("Shotgunning '%s' for %d followers" % (shotgunUser, numFollowers))
        c = 0
        x = 0
        try:
            for f in tweepy.Cursor(api.followers, shotgunUser).items():
                x += 1
                id = f.id
                if id in data['wasFollowing']:
                    info("%d '%s' following or was following." % (x, f.screen_name))
                elif id in data['wasFollowedBy']:
                    info("%d '%s' followed by or was followed." % (x, f.screen_name))
                elif f.protected:
                    info("%d '%s' is protected." % (x, f.screen_name))
                elif f.followers_count <= shotgunTargetMinFollowers:
                    info("%d '%s' not enough followers." % (x, f.screen_name))
                elif f.friends_count <= shotgunTargetMinFollowing:
                    info("%d '%s' not following enough." % (x, f.screen_name))
                elif f.description == "":
                    info("%d '%s' empty description." % (x, f.screen_name))
                elif f.statuses_count <= shotgunTargetMinTweets:
                    info("%d '%s' not enough tweets." % (x, f.screen_name))
                elif f.screen_name == username:
                    info("%d '%s' can't follow yourself!" % (x, f.screen_name))
                else:
                    api.create_friendship(f.id)
                    c += 1
                    info("%d '%s' FOLLOWED(%d)." % (x, f.screen_name, c))
                    time.sleep(3)
                if (c == numFollowers):
                    break;
        except tweepy.error.TweepError, e:
            print ""
            if e.message[0]['message'] == u'Rate limit exceeded':
                info("Rate limit exceeded")
            else:
                print traceback.format_exc()
                raise e
        update(api, data)

    elif command == "ignore":
        if len(argv) != 2:
            error("Missing params user")
        user = api.get_user(argv[1])
        api.destroy_friendship(user.id)
        data['wasFollowing'].add(user.id)
        print "'%s' ignored." % (user.screen_name)

    else:
        error("Unknown command '%s'" % command)

    #print api.me().name
    rate = api.rate_limit_status()
    #pp.pprint(rate)
    print ""
    data.close()


if __name__ == "__main__":
    main(sys.argv[1:])
