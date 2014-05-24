table_row_selector = """//table[@class = "records-table toggled-table condensedTbl"]/tr[@id]"""

tasks = [
    Task(
        name="Leichthatletik_Sprint_100m_Herren",  # task name
        url_generator="http://www.iaaf.org/records/toplists/sprints/100-metres/outdoor/men/senior",
        selectors=[
            Task.Selector(name="athlete_id", xpath=table_row_selector + "/td[4]/a/@href", type=int),
            Task.Selector(name="first_name", xpath=table_row_selector + "/td[4]/a/text()", type=unicode),
            Task.Selector(name="last_name", xpath=table_row_selector + "/td[4]/a/span/text()", type=unicode),
            Task.Selector(name="result_time", xpath=table_row_selector + "/td[2]/text()", type=float),
            Task.Selector(name="competition_date", xpath=table_row_selector + "/td[9]/text()", type=datetime.datetime),
        ],
    ),
    Task(
        name="Leichthatletik_Athleten",  # task name
        url_generator="[http://www.iaaf.org/athletes/athlete=%s][Leichthatletik_Sprint_100m_Herren][athlete_id]",
        selectors=[
            Task.Selector(name="athlete_id", xpath="""//meta[@property = "og:url"]/@content""", type=int),
            Task.Selector(name="name", xpath="""//div[@class = "name-container athProfile"]/h1/text()""", type=unicode),
            Task.Selector(name="birthday", xpath="""//div[@class = "country-date-container"]//span[4]//text()""", type=datetime.datetime),
            Task.Selector(name="country", xpath="""//div[@class = "country-date-container"]//span[2]//text()""", type=unicode),
        ],
    ),

    Task(
        name="Kaltmieten_Muenchen",  # task name
        table_name="Wohnungen",
        url_generator="http://www.immobilienscout24.de/Suche/S-T/Wohnung-Miete/Bayern/Muenchen",
        selectors=[
            Task.Selector(name="wohnungs_id", xpath="""//span[@class="title"]//a/@href""", type=int),
            Task.Selector(name="naechste_seite", xpath="""//span[@class="nextPageText"]/..//@href"""),
        ],
    ),
    Task(
        name="Kaltmieten_Berlin",  # task name
        table_name="Wohnungen",
        url_generator="http://www.immobilienscout24.de/Suche/S-T/Wohnung-Miete/Berlin/Berlin",
        selectors=[
            Task.Selector(name="wohnungs_id", xpath="""//span[@class="title"]//a/@href""", type=int),
            Task.Selector(name="naechste_seite", xpath="""//span[@class="nextPageText"]/..//@href"""),
        ],
    ),
    Task(
        name="Kaltmieten_Rec",  # task name
        table_name="Wohnungen",
        url_generator="[http://www.immobilienscout24.de%s][Wohnungen][naechste_seite]",
        selectors=[
            Task.Selector(name="wohnungs_id", xpath="""//span[@class="title"]//a/@href""", type=int),
            Task.Selector(name="naechste_seite", xpath="""//span[@class="nextPageText"]/..//@href"""),
        ],
    ),

    Task(
        name="Wohnungsdetails",  # task name
        url_generator="[http://www.immobilienscout24.de/expose/%s][Wohnungen][wohnungs_id]",
        selectors=[
            Task.Selector(name="wohnungs_id", xpath="""//a[@id="is24-ex-remember-link"]/@href""", type=int),
            Task.Selector(name="postleitzahl", xpath="""//div[@data-qa="is24-expose-address"]//text()""", type=int, regex="\d{5}"),
            Task.Selector(name="zimmeranzahl", xpath="""//dd[@class="is24qa-zimmer"]//text()""", type=int),
            Task.Selector(name="wohnflaeche", xpath="""//dd[@class="is24qa-wohnflaeche-ca"]//text()""", type=int),
            Task.Selector(name="kaltmiete", xpath="""//dd[@class="is24qa-kaltmiete"]//text()""", type=int),
        ],
    ),
]