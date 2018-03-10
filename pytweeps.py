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
import collections
from datetime import datetime
from datetime import timedelta
from config import *
import io
import urllib2

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
    if 'wasFollowing' not in data.keys():
        data['wasFollowing'] = set()
    if 'followers' not in data.keys():
        data['followers'] = set()
    if 'wasFollowedBy' not in data.keys():
        data['wasFollowedBy'] = set()
    if 'lastTweet' not in data.keys():
        data['lastTweet'] = dict()
    if 'followedOn' not in data.keys():
        data['followedOn'] = dict()
    if 'wasFollowingOn' not in data.keys():
        data['wasFollowingOn'] = dict()
    data.sync()


def follow(api, data, user):
    api.create_friendship(user.id)
    data['followedOn'][user.id] = datetime.now()


def authenticate(auth, data):
    redirect_url = auth.get_authorization_url()
    webbrowser.open(redirect_url)
    try:
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
    print "    bury daysSinceLastTweet numberToUnfollow"
    print "        Remove any 'dead' tweeps. i.e. followers who no longer use twitter"
    print "    requite daysSinceFollowed numberToUnfollow"
    print "        Remove any tweeps who do not continue to follow you after daysSinceFollowed days"
    print "    shotgun user numTweeps "
    print "        Add numTweeps followers from a user. Doesn't follow previously followed users."
    print "    copycat user numTweeps"
    print "        Add numTweeps from the list of tweeps user is following.  Doesn't follow previously followed users."
    print "    copykids numKids numTweeps"
    print "        Add numKids from *every* person you follow's following list.  Stop after adding (approximately) numTweeps total."
    print "    ignore user"
    print "        Ignore a particular user, never try to follow them and unfollow if we are following."
    print "    follow user"
    print "        Follow a particular user, even if we retired them already."
    print "    unfollowers filename"
    print "        prints a list of unfollowers to filename"


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
        if id not in data['followedOn']:
            data['followedOn'][id] = datetime.now()

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


def copycat(api, data, copycatUser, numTweeps):
    c = 0
    x = 0
    for f in tweepy.Cursor(api.friends, copycatUser).items():
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
        if (c == numTweeps):
            break;
    return c


def main(argv):
    pp = pprint.PrettyPrinter(indent=4)

    print "\nPyTweeps v0.1 - using tweepy v%s\n" % pkg_resources.get_distribution('tweepy').version

    if len(argv) == 0:
        usageMessage()
        sys.exit(-1)

    data = shelve.open('pytweeps', writeback=True)
    initData(data)

    auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
    auth.secure = True
    if ('access_token_key' not in data.keys()) or ('access_token_secret' not in data.keys()):
        authenticate(auth, data)
    auth.set_access_token(data['access_token_key'], data['access_token_secret'])

    api = tweepy.API(auth)

    command = argv[0]
    if command == "update":
        update(api, data)

    elif command == "bury":
        # Check params
        if len(argv) < 3:
            error("Missing params daysSinceLastTweet or numberToUnfollow")
        if not isInt(argv[1]):
            error("daysSinceLastTweet is not an integer")
        daysSinceLastTweet = int(argv[1])
        if not isInt(argv[2]):
            error("numberToUnfollow is not an integer")
        numberToUnfollow = int(argv[2])
        delay = 0
        if len(argv) >= 4 and isInt(argv[3]):
            delay = argv[3]

        # death date is the cut off. if they haven't tweeted since then, bury them
        cutoffDate = datetime.now() - timedelta(days=daysSinceLastTweet)

        # Check the lastTweet cache, if their last tweet isn't after the cutoffDate don't bother checking against twitter
        last = data['lastTweet']
        lastKeys = last.keys()
        toScan = set()
        for f in data['following']:
            if f in lastKeys:
                if last[f] < cutoffDate:
                    toScan.add(f)
                    # else don't bother checking
            else:
                # not in cache, so check
                toScan.add(f)

        x = 0
        numUnfollowed = 0
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
                        numUnfollowed += 1
                else:
                    lastTweet = tweets[0]
                    if (lastTweet.created_at < cutoffDate):
                        if lastTweet.user.screen_name not in neverBury:
                            api.destroy_friendship(f)
                            print ""
                            info("Buried '%s' R.I.P. (Last: %s)" % (
                                lastTweet.user.screen_name, unicode(lastTweet.created_at)))
                            numUnfollowed += 1
                    else:
                        data['lastTweet'][f] = lastTweet.created_at
                        data.sync()

                if numUnfollowed == numberToUnfollow:
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

    elif command == "requite":

        # Check params
        if len(argv) < 3:
            error("Missing params daysSinceFollowed or numberToUnfollow")
        if not isInt(argv[1]):
            error("daysSinceFollowed is not an integer")
        daysSinceFollowed = int(argv[1])
        if not isInt(argv[2]):
            error("numberToUnfollow is not an integer")
        numberToUnfollow = int(argv[2])
        delay = 0
        if len(argv) >= 4 and isInt(argv[3]):
            delay = argv[3]

        # death date is the cut off. if they haven't tweeted since then, bury them
        cutoffDate = datetime.now() - timedelta(days=daysSinceFollowed)

        # Check the wasFollowingOn cache, if their last tweet isn't after the cutoffDate don't bother checking against twitter
        last = data['wasFollowingOn']
        lastKeys = last.keys()
        followedOn = data['followedOn']
        followedOnKeys = followedOn.keys()
        toScan = set()
        for f in data['following']:
            if f in lastKeys:
                if last[f] < cutoffDate:
                    toScan.add(f)
                    # else don't bother checking
            elif f in followedOnKeys:
                if followedOn[f] < cutoffDate:
                    toScan.add(f)
            else:
                # doesn't have a followedOn date, so check
                data['followedOn'][f] = datetime.now()
                data.sync()
                toScan.add(f)

        print "Requiting %d tweeps.  %d IDs to scan" % (numberToUnfollow, len(toScan))

        x = 0
        numUnfollowed = 0
        me = api.me()
        try:
            for f in toScan:
                try:
                    user = api.get_user(f)
                except tweepy.error.TweepError, e:
                    if isinstance(e.message, collections.Iterable):
                        if e.message[0]['message'] == u'User not found.':
                            info("User not found, skipping...")
                        else:
                            print traceback.format_exc()
                            raise e

                ref = api.show_friendship(source_id=f, target_id=me.id)
                if ref[0].following:
                    # User follows me
                    data['wasFollowingOn'][f] = datetime.now()
                    data.sync()
                else:
                    # User not following me
                    user = api.get_user(f)
                    if user.screen_name not in neverBury:
                        api.destroy_friendship(f)
                        print ""
                        info("Requited '%s' (Followed On: %s)" % (user.screen_name, unicode(data['followedOn'][f])))
                        numUnfollowed += 1
                        # else still has time to follow
                if numUnfollowed == numberToUnfollow:
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
            pp.pprint(e)
            if isinstance(e.message, collections.Iterable):
                if e.message[0]['message'] == u'Rate limit exceeded':
                    info("Rate limit exceeded")
                else:
                    print traceback.format_exc()
                    raise e
            else:
                print traceback.format_exc()
                raise e

        print ""
        update(api, data)

    elif command == "shotgun":
        if len(argv) != 3:
            error("Missing params shotgun user or numTweeps")
        shotgunUser = argv[1]
        if not isInt(argv[2]):
            error("numTweeps is not an integer")
        numTweeps = int(argv[2])
        info("Shotgunning '%s' for %d followers" % (shotgunUser, numTweeps))
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
                    try:
                        api.create_friendship(f.id)
                        c += 1
                        info("%d '%s' FOLLOWED(%d)." % (x, f.screen_name, c))
                    except tweepy.error.TweepError, e:
                        print ""
                        if e.message[0]['code'] == 162:
                            info("%d '%s' blocked you." % (x, f.screen_name))
                            api.destroy_friendship(f.id)
                            data['wasFollowing'].add(f.id)
                        else:
                            print traceback.format_exc()
                            raise e
                    time.sleep(3)
                if (c == numTweeps):
                    break;
        except tweepy.error.TweepError, e:
            print ""
            if e.message[0]['message'] == u'Rate limit exceeded':
                info("Rate limit exceeded")
            else:
                print traceback.format_exc()
                raise e
        update(api, data)

    elif command == "copycat":
        if len(argv) != 3:
            error("Missing params copycat user or numTweeps")
        copycatUser = argv[1]
        if not isInt(argv[2]):
            error("numTweeps is not an integer")
        numTweeps = int(argv[2])
        info("Copycatting '%s' for %d followers" % (copycatUser, numTweeps))
        try:
            copycat(api, data, copycatUser, numTweeps)
        except tweepy.error.TweepError, e:
            print ""
            if e.message[0]['message'] == u'Rate limit exceeded':
                info("Rate limit exceeded")
            else:
                print traceback.format_exc()
                raise e
        update(api, data)

    elif command == "copykids":
        if len(argv) != 3:
            error("Missing params numKids or numTweeps")
        if not isInt(argv[1]):
            error("numKids is not an integer")
        numKids = int(argv[1])
        if not isInt(argv[2]):
            error("numTweeps is not an integer")
        numTweeps = int(argv[2])
        info("Copykidding %d follwers from each of your followers. %d followers total." % (numKids, numTweeps))
        try:
            c = 0
            for f in tweepy.Cursor(api.followers).items():
                info("********")
                c += copycat(api, data, f, numKids)
                if (c >= numTweeps):
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

    elif command == "follow":
        if len(argv) != 2:
            error("Missing params user")
        user = api.get_user(argv[1])
        follow(api, data, user)
        if (user.id in data['wasFollowing']):
            data['wasFollowing'].remove(user.id)
        print "'%s' FOLLOWED." % (user.screen_name)

    elif command == "unfollow":
        if len(argv) != 2:
            error("Missing param fileName")
        with io.open(argv[1], 'r', encoding='utf8') as f:
            for line in f:
                s = line.split("|",3)
                if s[0] == 'x':
                    api.destroy_friendship(s[1])
                    print "Unfollowed", s[2]

    elif command == "unfollowers":
        if len(argv) != 2:
            error("Missing param fileName")
        old = []
        ids = set()
        try:
            with io.open(argv[1], 'r', encoding='utf8') as f:
                for line in f:
                    s = line.split("|",3)
                    old.append(s)
                    ids.add(int(s[1]))
        except:
            pass
        print "Creating a list of unfollowers to %s" % argv[1]
        me = api.me()
        c = 0
        with io.open(argv[1], 'a', encoding='utf8') as f:
            for id in api.friends_ids():
                print [id], id in ids
                if id not in ids:
                    ref = api.show_friendship(source_id=id, target_id=me.id)
                    if not ref[0].following:
                        # User doesn't follow me
                        user = api.get_user(id)
                        desc = user.description.replace("\n",'').replace("\r",'')
                        try:
                            if user.url:
                                req = urllib2.urlopen(user.url)
                                url = req.url
                            else:
                                url = ""
                        except:
                            url = ""
                        f.write("|%s|%s|%s|%s|%s\n" % (id, user.screen_name, user.name, desc, url))
                        f.flush()
                    time.sleep(3)
                c += 1
                sys.stdout.write('.')
                if c % 100 == 0:
                    sys.stdout.write("[" + str(c) + "]")
                sys.stdout.flush()

    else:
        error("Unknown command '%s'" % command)

    #print api.me().name
    rate = api.rate_limit_status()
    #pp.pprint(rate)
    print ""
    data.close()


if __name__ == "__main__":
    main(sys.argv[1:])
