PyTweeps
========

Simple Python program to help manage your twitter followers.

Supported Commands
==================
    update
        Updates your list of followers and followed
    bury daysSinceLastTweet numberToBury [secondsBetweenUser]
        Remove any 'dead' tweeps. i.e. followers who no longer use twitter
    shotgun user numFollowers
        Add numFollowers followers from a user. Users no longer following and followed by are skipped
    ignore user
        Ignore a particular user, never try to follow them and unfollow if we are following.
