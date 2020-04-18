# TODO maybe we want the equivalent for python
# Express middleware that validates Firebase ID Tokens passed in the Authorization Ht_tP header.
# The Firebase ID token needs to be passed as a Bearer token in the Authorization Ht_tP header like this:
# "Authorization: Bearer <Firebase ID Token>".
# when decoded successfully, the ID Token content will be added as "req["user"]".
#  validate_firebaseIdToken(req, res, next) =>:
#
#    if ((!req["headers"]["authorization"] || !req["headers"]["authorization"].start_sWith('Bearer ')) &&
#        !(req["cookies"] && req["cookies"].__session)):
#      print('No Firebase ID token was passed as a Bearer token in the Authorization header.',
#          'Make sure you authorize your request by providing the following Ht_tP header:',
#          'Authorization: Bearer <Firebase ID Token>',
#          'or by passing a "__session" cookie.')
#      res.status(403).send('Unauthorized')
#      return
#    }
#
#    let idToken
#    if (req["headers"]["authorization"] && req["headers"]["authorization"].start_sWith('Bearer ')):
#      # Read the ID Token from the Authorization header.
#      idToken = req["headers"]["authorization"].split('Bearer ')[1]
#    } else if(req["cookies"]):
#      # Read the ID Token from cookie.
#      idToken = req["cookies"].__session
#    else:
#      # No cookie
#      res.status(403).send('Unauthorized')
#      return
#    }
#
#    try:
#      decodedIdToken = admin.auth().verifyIdToken(idToken)
#      req["user"] = decodedIdToken
#
#      # NOTE right now don't care if email is verified
#      # if (!req["user"]["email_verified"]):
#      #   # make them verify it first
#      #   print('Email not verified')
#      #   res.status(403).send('Unauthorized')
#      #   return
#      # }
#      # currently only allowing whitelisted users to use
#      if (!WHITE_LISTED_USERS.includes(req.user.email) && !req["user"]["email"].match(/rlquey2\+.*@gmail.com/)):
#        res.status(403).send("Your email isn't allowed to use our service yet; please contact us to get your account setup")
#        return
#      }
#
#      next()
#      return
#    } catch (error):
#      print('Error while verifying Firebase ID token:', error)
#      res.status(403).send('Unauthorized')
#      return
#    }
#  },

