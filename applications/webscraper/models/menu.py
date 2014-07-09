# -*- coding: utf-8 -*-
# this file is released under public domain and you can use without limitations

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

#########################################################################
## this is the main application menu add/remove items as required
#########################################################################

response.menu = [
    (T('Home'), False, URL('default', 'index'), []),

    (SPAN('Reload Tasks'), False, URL('ajax', 'add_tasks'),
     [(task.name, False, URL('ajax', 'view_data', vars={"name": task.name})) for task in Task.get_all()]),

    (T('Database'), False, URL('appadmin', 'index')),

    (T('Administration'), False, URL('admin', 'default', 'site')),
]