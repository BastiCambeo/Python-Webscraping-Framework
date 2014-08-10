# -*- coding: utf-8 -*-

## if SSL/HTTPS ##
#if not request.is_local and request.controller != "taskqueue":
    #request.requires_https()


## connect to Google BigTable (optional 'google:datastore://namespace')
db = DAL('google:datastore')
## store sessions and tickets there
from datetime import datetime, timedelta
session.connect(request, response, db=db, cookie_expires=datetime.now() + timedelta(days=30))


#########################################################################
## - email capabilities
## - authentication (registration, login, logout, ... )
## - authorization (role based authorization)
## - services (xml, csv, json, xmlrpc, jsonrpc, amf, rss)
#########################################################################

from gluon.tools import Auth, Crud, Service, PluginManager, prettydate
auth = Auth(db)
crud, service, plugins = Crud(db), Service(), PluginManager()

## create all tables needed by auth if not custom tables ##
auth.define_tables(username=False, signature=False)

## configure email ##
mail = auth.settings.mailer
mail.settings.server = 'logging' or 'smtp.gmail.com:587'
mail.settings.sender = 'basti@katseb.de'
mail.settings.login = 'basti@katseb.de:password'

## configure auth policy ##
auth.settings.expiration = auth.settings.long_expiration
auth.settings.registration_requires_verification = False
auth.settings.registration_requires_approval = False
auth.settings.reset_password_requires_verification = False

#########################################################################
## Customize your APP title, subtitle and menus here
#########################################################################

response.logo = A(B('Web',SPAN('Scraper')),XML('&copy;&nbsp;'), _class="brand",_href="/")
response.title = 'Webscraper'
response.subtitle = ''

## read more at http://dev.w3.org/html5/markup/meta.name.html
response.meta.author = 'Sebastian Hofstetter'
response.meta.keywords = 'webscraper, web2py, python, framework'
response.meta.generator = 'Web2py Web Framework'

## your http://google.com/analytics id
response.google_analytics_id = None