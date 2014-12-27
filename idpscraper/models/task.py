__author__ = 'Sebastian Hofstetter'

import itertools
from idpscraper.models import UrlSelector, Selector, Result
from django.db import models
import logging
from lxml import html, etree  # xpath support
from requests import Session  # for login required http requests
import re
import time

class Task(models.Model):
    """ A Webscraper Task """

    name = models.TextField(primary_key=True)

    @property
    def recursive_url_selectors(self):
        return [url_selector for url_selector in self.url_selectors.all() if url_selector.has_dynamic_url and url_selector.selector_task_id == self.pk]

    def __str__(self):
        return self.name

    def get_urls(self, results=None, limit=None):
        return itertools.chain(*[url_selector.get_urls(results=results, limit=limit) for url_selector in self.url_selectors.all()])  # Keep generators intact!

    @staticmethod
    def get(name):
        return Task.objects.get(pk=name)

    def as_table(self, results):
        yield tuple(selector.name for selector in self.selectors.all())

        for result in results:
            yield tuple(getattr(result, selector.name) if hasattr(result, selector.name) else None for selector in self.selectors.all())

    def run(self, limit=None, store=True) -> 'list[Result]':
        urls = set(self.get_urls(limit=limit))
        visited_urls = set()
        all_results = []

        while len(urls) > 0:
            logging.error("Remaining: %s" % len(urls))
            url = urls.pop()
            if url not in visited_urls:
                visited_urls.add(url)

                # Fetch Result #
                results = self.http_request(url)
                all_results += results

                if store and results:
                    # Store result in database #
                    for result in results:
                        result.save()

                    # Schedule new urls on recursive call #
                    if self.recursive_url_selectors:
                        urls.update(self.recursive_url_selectors[0].get_urls(results=results))

        return all_results

    def test(self):
        return self.run(limit=1, store=False)

    def export(self):
        return ",\n".join([repr(m) for m in [self] + self.selectors.all() + self.url_selectors.all()])

    def export_to_excel(self):
        return Task.export_data_to_excel(data=self.as_table(self.results.all()))

    @staticmethod
    def export_data_to_excel(data):
        import xlwt  # Excel export support
        import io  # for files in memory

        w = xlwt.Workbook()
        ws = w.add_sheet("data")

        # write #
        for x, row in enumerate(data):
            for y, column in enumerate(row):
                ws.write(x, y, column)

        # save #
        f = io.BytesIO()
        w.save(f)
        del w, ws
        f.seek(0)
        return f.read()

    @staticmethod
    def example_tasks() -> 'list[Task]':
        Task.objects.all().delete()
        UrlSelector.objects.all().delete()
        Selector.objects.all().delete()

        mods = [
            Task(name="Fussball_Einsaetze"),
            UrlSelector(task_id='Fussball_Einsaetze', url="http://www.transfermarkt.de/spieler/leistungsdatendetails/spieler/%s/plus/1/saison/%s", selector_task_id='Fussball_Spieler', selector_name="spieler_id", selector_name2="saison"),
            Selector(task_id='Fussball_Einsaetze', name="spieler_id", is_key=True, xpath='''(//a[@class="megamenu"])[1]/@href''', type=0, regex="\\d[\\d.,]*"),
            Selector(task_id='Fussball_Einsaetze', name="minutes_played", is_key=False, xpath='''//div[@class="responsive-table"]/table//tr/td[2]/following-sibling::*[last()]''', type=0, regex="\\d[\\d.,]*"),
            Selector(task_id='Fussball_Einsaetze', name="date", is_key=True, xpath='''//div[@class="responsive-table"]/table//tr/td[2]''', type=2, regex="[^\\n\\r ,.][^\\n\\r]+"),

            Task(name="Fussball_Saisons"),
            UrlSelector(task_id='Fussball_Saisons', url="http://www.transfermarkt.de/3262/kader/verein/3262/", selector_task_id='Fussball_Saisons', selector_name="saison", selector_name2="saison"),
            Selector(task_id='Fussball_Saisons', name="saison", is_key=True, xpath='''//select[@name="saison_id"]/option/@value''', type=0, regex="2004"),

            Task(name="Fussball_Spieler"),
            UrlSelector(task_id='Fussball_Spieler', url="http://www.transfermarkt.de/%s", selector_task_id='Fussball_Vereine', selector_name="verein_url", selector_name2="verein_url"),
            Selector(task_id='Fussball_Spieler', name="spieler_id", is_key=True, xpath='''//a[@class="spielprofil_tooltip"]/@href''', type=0, regex="\\d[\\d.,]*"),
            Selector(task_id='Fussball_Spieler', name="saison", is_key=True, xpath='''//select[@name="saison_id"]/option[@selected="selected"]/@value''', type=0, regex="\\d[\\d.,]*"),

            Task(name="Fussball_Spieler_Details"),
            UrlSelector(task_id='Fussball_Spieler_Details', url="http://www.transfermarkt.de/daten/profil/spieler/%s", selector_task_id='Fussball_Spieler', selector_name="spieler_id", selector_name2="spieler_id"),
            Selector(task_id='Fussball_Spieler_Details', name="spieler_id", is_key=True, xpath='''//link[@rel="canonical"]/@href''', type=0, regex="\\d[\\d.,]*"),
            Selector(task_id='Fussball_Spieler_Details', name="name", is_key=False, xpath='''//div[@class="spielername-profil"]/text()''', type=1, regex="[^\\n\\r ,.][^\\n\\r]+"),
            Selector(task_id='Fussball_Spieler_Details', name="position", is_key=False, xpath='''//table[@class="profilheader"]//td[preceding-sibling::th/text()="Position:"]''', type=1, regex="[^\\n\\r ,.][^\\n\\r]+"),
            Selector(task_id='Fussball_Spieler_Details', name="max_value", is_key=False, xpath='''//table[@class="auflistung mt10"]/tr[3]/td/text()''', type=3, regex="\\d[\\d.,:]*"),
            Selector(task_id='Fussball_Spieler_Details', name="birthday", is_key=False, xpath='''//td[preceding-sibling::th/text()="Geburtsdatum:"]/a/text()''', type=2, regex="[^\\n\\r ,.][^\\n\\r]+"),
            Selector(task_id='Fussball_Spieler_Details', name="size", is_key=False, xpath='''//td[preceding-sibling::th/text()="GrÃ¶ÃŸe:"]//text()''', type=3, regex="\\d[\\d.,:]*"),
            Selector(task_id='Fussball_Spieler_Details', name="retire_date", is_key=False, xpath='''//table[@class="profilheader"]//td[preceding-sibling::*[.//@title="Karriereende"]]''', type=2, regex="[^\\n\\r ,.][^\\n\\r]+"),

            Task(name="Fussball_Transfers"),
            UrlSelector(task_id='Fussball_Transfers', url="http://www.transfermarkt.de/daten/profil/spieler/%s", selector_task_id='Fussball_Spieler', selector_name="spieler_id", selector_name2=""),
            Selector(task_id='Fussball_Transfers', name="spieler_id", is_key=False, xpath='''(//a[@class="megamenu"])[1]/@href''', type=0, regex="\\d[\\d.,]*"),
            Selector(task_id='Fussball_Transfers', name="date", is_key=False, xpath='''(//table)[3]//tr/td[2]//text()''', type=2, regex="[^\\n\\r ,.][^\\n\\r]+"),
            Selector(task_id='Fussball_Transfers', name="from", is_key=False, xpath='''(//table)[3]//tr/td[5]/a/text()''', type=1, regex="[^\\n\\r ,.][^\\n\\r]+"),
            Selector(task_id='Fussball_Transfers', name="to", is_key=False, xpath='''(//table)[3]//tr/td[8]/a/text()''', type=1, regex="[^\\n\\r ,.][^\\n\\r]+"),
            Selector(task_id='Fussball_Transfers', name="transfer_key", is_key=True, xpath='''merge_lists((//a[@class="megamenu"])[1]/@href, (//table)[3]//tr/td[5]/a/text(), (//table)[3]//tr/td[8]/a/text())''', type=1, regex="[^\\n\\r ,.][^\\n\\r]+"),

            Task(name="Fussball_Vereine"),
            UrlSelector(task_id='Fussball_Vereine', url="http://www.transfermarkt.de/1-bundesliga/startseite/wettbewerb/L1/saison_id/%s", selector_task_id='Fussball_Saisons', selector_name="saison", selector_name2="saison"),
            Selector(task_id='Fussball_Vereine', name="verein_url", is_key=True, xpath='''//table[@class='items']//tr/td[@class='hauptlink no-border-links']/a[1]/@href''', type=1, regex="[^\\n\\r ,.][^\\n\\r]+"),

            Task(name="Fussball_Verletzungen"),
            UrlSelector(task_id='Fussball_Verletzungen', url="http://www.transfermarkt.de/spieler/verletzungen/spieler/%s", selector_task_id='Fussball_Spieler', selector_name="spieler_id", selector_name2="spieler_id"),
            UrlSelector(task_id='Fussball_Verletzungen', url="http://www.transfermarkt.de%s", selector_task_id='Fussball_Verletzungen', selector_name="next_page", selector_name2="spieler_id"),
            Selector(task_id='Fussball_Verletzungen', name="spieler_id", is_key=True, xpath='''(//a[@class="megamenu"])[1]/@href''', type=0, regex="\\d[\\d.,]*"),
            Selector(task_id='Fussball_Verletzungen', name="injury", is_key=False, xpath='''//table[@class="items"]//tr/td[2]/text()''', type=1, regex="[^\\n\\r ,.][^\\n\\r]+"),
            Selector(task_id='Fussball_Verletzungen', name="from", is_key=True, xpath='''//table[@class="items"]//tr/td[3]/text()''', type=2, regex="[^\\n\\r ,.][^\\n\\r]+"),
            Selector(task_id='Fussball_Verletzungen', name="to", is_key=False, xpath='''//table[@class="items"]//tr/td[4]/text()''', type=2, regex="[^\\n\\r ,.][^\\n\\r]+"),
            Selector(task_id='Fussball_Verletzungen', name="duration", is_key=False, xpath='''//table[@class="items"]//tr/td[5]/text()''', type=0, regex="\\d[\\d.,]*"),
            Selector(task_id='Fussball_Verletzungen', name="missed_games", is_key=False, xpath='''//table[@class="items"]//tr/td[6]/text()''', type=0, regex="\\d[\\d.,]*"),
            Selector(task_id='Fussball_Verletzungen', name="next_page", is_key=False, xpath='''//li[@class="naechste-seite"]/a/@href''', type=1, regex="[^\\n\\r ,.][^\\n\\r]+"),
            Selector(task_id='Fussball_Verletzungen', name="club", is_key=False, xpath='''exe(//table[@class="items"]//tr/td[6],".//@title")''', type=1, regex="[^\\n\\r ,.][^\\n\\r]+"),

            Task(name="Leichtathletik_Athleten"),
            UrlSelector(task_id='Leichtathletik_Athleten', url="http://www.iaaf.org/athletes/search?name=&country=&discipline=%s&gender=", selector_task_id='Leichtathletik_Disziplinen', selector_name="disciplin", selector_name2=""),
            Selector(task_id='Leichtathletik_Athleten', name="athlete_id", is_key=True, xpath='''//table[@class="records-table"]//tr[not(@class)]/td[1]//@href''', type=0, regex="\\d[\\d.,]*"),
            Selector(task_id='Leichtathletik_Athleten', name="first_name", is_key=False, xpath='''//table[@class="records-table"]//tr[not(@class)]/td[1]//a/text()''', type=1, regex="[^\\n\\r ,.][^\\n\\r]+"),
            Selector(task_id='Leichtathletik_Athleten', name="last_name", is_key=False, xpath='''//table[@class="records-table"]//tr[not(@class)]/td[1]/a/span/text()''', type=1, regex="[^\\n\\r ,.][^\\n\\r]+"),
            Selector(task_id='Leichtathletik_Athleten', name="sex", is_key=False, xpath='''//table[@class="records-table"]//tr[not(@class)]/td[2]/text()''', type=1, regex="[^\\n\\r ,.][^\\n\\r]+"),
            Selector(task_id='Leichtathletik_Athleten', name="country", is_key=False, xpath='''//table[@class="records-table"]//tr[not(@class)]/td[3]/text()''', type=1, regex="[^\\n\\r ,.][^\\n\\r]+"),
            Selector(task_id='Leichtathletik_Athleten', name="birthday", is_key=False, xpath='''//table[@class="records-table"]//tr[not(@class)]/td[4]/text()''', type=2, regex="[^\\n\\r ,.][^\\n\\r]+"),

            Task(name="Leichtathletik_Disziplinen"),
            UrlSelector(task_id='Leichtathletik_Disziplinen', url="http://www.iaaf.org/athletes", selector_task_id='Leichtathletik_Disziplinen', selector_name="disciplin", selector_name2=""),
            Selector(task_id='Leichtathletik_Disziplinen', name="disciplin", is_key=True, xpath='''//select[@id="selectDiscipline"]/option/@value''', type=1, regex=""),

            Task(name="Leichtathletik_Performance"),
            UrlSelector(task_id='Leichtathletik_Performance', url="http://www.iaaf.org/athletes/athlete=%s", selector_task_id='Leichtathletik_Athleten', selector_name="athlete_id", selector_name2=""),
            Selector(task_id='Leichtathletik_Performance', name="athlete_id", is_key=False, xpath='''//meta[@name="url"]/@content''', type=0, regex="\\d[\\d.,]*"),
            Selector(task_id='Leichtathletik_Performance', name="performance", is_key=False, xpath='''//div[@id="panel-progression"]//tr[count(td)>3]//td[2]''', type=3, regex="\\d[\\d.,:]*"),
            Selector(task_id='Leichtathletik_Performance', name="datetime", is_key=False, xpath='''merge_lists(//div[@id="panel-progression"]//tr[count(td)>3]/td[last()], //div[@id="panel-progression"]//tr[count(td)>3]/td[1])''', type=2, regex="[^\\n\\r ,.][^\\n\\r]+"),
            Selector(task_id='Leichtathletik_Performance', name="place", is_key=False, xpath='''//div[@id="panel-progression"]//tr[count(td)>3]//td[last()-1]''', type=1, regex="[^\\n\\r ,.][^\\n\\r]+"),
            Selector(task_id='Leichtathletik_Performance', name="discipline", is_key=False, xpath='''exe(//div[@id="panel-progression"]//tr[count(td)>3]//td[2], "../preceding::tr/td[@class='sub-title']")''', type=1, regex="[^\\n\\r ,.][^\\n\\r]+"),
            Selector(task_id='Leichtathletik_Performance', name="performance_key", is_key=True, xpath='''merge_lists(//div[@id="panel-progression"]//tr[count(td)>3]/td[last()], //div[@id="panel-progression"]//tr[count(td)>3]/td[1], //meta[@name="url"]/@content)''', type=1, regex="[^\\n\\r ,.][^\\n\\r]+"),

            Task(name="Leichtathletik_Sprint_100m_Herren"),
            UrlSelector(task_id='Leichtathletik_Sprint_100m_Herren', url="http://www.iaaf.org/records/toplists/sprints/100-metres/outdoor/men/senior", selector_task_id='Leichtathletik_Sprint_100m_Herren', selector_name="athlete_id", selector_name2=""),
            Selector(task_id='Leichtathletik_Sprint_100m_Herren', name="athlete_id", is_key=True, xpath='''//table[@class = "records-table toggled-table condensedTbl"]/tr[@id]/td[4]/a/@href''', type=0, regex="\\d[\\d.,]*"),
            Selector(task_id='Leichtathletik_Sprint_100m_Herren', name="first_name", is_key=False, xpath='''//table[@class = "records-table toggled-table condensedTbl"]/tr[@id]/td[4]/a/text()''', type=1, regex="[^\\n\\r ,.][^\\n\\r]+"),
            Selector(task_id='Leichtathletik_Sprint_100m_Herren', name="last_name", is_key=False, xpath='''//table[@class = "records-table toggled-table condensedTbl"]/tr[@id]/td[4]/a/span/text()''', type=1, regex="[^\\n\\r ,.][^\\n\\r]+"),
            Selector(task_id='Leichtathletik_Sprint_100m_Herren', name="result_time", is_key=False, xpath='''//table[@class = "records-table toggled-table condensedTbl"]/tr[@id]/td[2]/text()''', type=3, regex="\\d[\\d.,:]*"),
            Selector(task_id='Leichtathletik_Sprint_100m_Herren', name="competition_date", is_key=False, xpath='''//table[@class = "records-table toggled-table condensedTbl"]/tr[@id]/td[9]/text()''', type=2, regex="[^\\n\\r ,.][^\\n\\r]+"),

            Task(name="Leichtathletik_Top_Performance"),
            UrlSelector(task_id='Leichtathletik_Top_Performance', url="http://www.iaaf.org%s/1999", selector_task_id='Leichtathletik_Top_Urls', selector_name="url", selector_name2=""),
            UrlSelector(task_id='Leichtathletik_Top_Performance', url="http://www.iaaf.org%s/2000", selector_task_id='Leichtathletik_Top_Urls', selector_name="url", selector_name2=""),
            UrlSelector(task_id='Leichtathletik_Top_Performance', url="http://www.iaaf.org%s/2001", selector_task_id='Leichtathletik_Top_Urls', selector_name="url", selector_name2=""),
            UrlSelector(task_id='Leichtathletik_Top_Performance', url="http://www.iaaf.org%s/2002", selector_task_id='Leichtathletik_Top_Urls', selector_name="url", selector_name2=""),
            UrlSelector(task_id='Leichtathletik_Top_Performance', url="http://www.iaaf.org%s/2003", selector_task_id='Leichtathletik_Top_Urls', selector_name="url", selector_name2=""),
            UrlSelector(task_id='Leichtathletik_Top_Performance', url="http://www.iaaf.org%s/2004", selector_task_id='Leichtathletik_Top_Urls', selector_name="url", selector_name2=""),
            UrlSelector(task_id='Leichtathletik_Top_Performance', url="http://www.iaaf.org%s/2005", selector_task_id='Leichtathletik_Top_Urls', selector_name="url", selector_name2=""),
            UrlSelector(task_id='Leichtathletik_Top_Performance', url="http://www.iaaf.org%s/2006", selector_task_id='Leichtathletik_Top_Urls', selector_name="url", selector_name2=""),
            UrlSelector(task_id='Leichtathletik_Top_Performance', url="http://www.iaaf.org%s/2007", selector_task_id='Leichtathletik_Top_Urls', selector_name="url", selector_name2=""),
            UrlSelector(task_id='Leichtathletik_Top_Performance', url="http://www.iaaf.org%s/2008", selector_task_id='Leichtathletik_Top_Urls', selector_name="url", selector_name2=""),
            UrlSelector(task_id='Leichtathletik_Top_Performance', url="http://www.iaaf.org%s/2009", selector_task_id='Leichtathletik_Top_Urls', selector_name="url", selector_name2=""),
            UrlSelector(task_id='Leichtathletik_Top_Performance', url="http://www.iaaf.org%s/2010", selector_task_id='Leichtathletik_Top_Urls', selector_name="url", selector_name2=""),
            UrlSelector(task_id='Leichtathletik_Top_Performance', url="http://www.iaaf.org%s/2011", selector_task_id='Leichtathletik_Top_Urls', selector_name="url", selector_name2=""),
            UrlSelector(task_id='Leichtathletik_Top_Performance', url="http://www.iaaf.org%s/2012", selector_task_id='Leichtathletik_Top_Urls', selector_name="url", selector_name2=""),
            UrlSelector(task_id='Leichtathletik_Top_Performance', url="http://www.iaaf.org%s/2013", selector_task_id='Leichtathletik_Top_Urls', selector_name="url", selector_name2=""),
            UrlSelector(task_id='Leichtathletik_Top_Performance', url="http://www.iaaf.org%s/2014", selector_task_id='Leichtathletik_Top_Urls', selector_name="url", selector_name2=""),
            Selector(task_id='Leichtathletik_Top_Performance', name="athlete_id", is_key=True, xpath='''(//table)[1]//tr[.//a and ./td[1] <= 20]//@href''', type=0, regex="\\d[\\d.,]*"),
            Selector(task_id='Leichtathletik_Top_Performance', name="first_name", is_key=False, xpath='''(//table)[1]//tr[.//a and ./td[1] <= 20]/td/a/text()''', type=1, regex="[^\\n\\r ,.][^\\n\\r]+"),
            Selector(task_id='Leichtathletik_Top_Performance', name="last_name", is_key=False, xpath='''(//table)[1]//tr[.//a and ./td[1] <= 20]/td/a/span/text()''', type=1, regex="[^\\n\\r ,.][^\\n\\r]+"),
            Selector(task_id='Leichtathletik_Top_Performance', name="performance", is_key=False, xpath='''(//table)[1]//tr[.//a and ./td[1] <= 20]/td[2]/text()''', type=3, regex="\\d[\\d.,:]*"),
            Selector(task_id='Leichtathletik_Top_Performance', name="datetime", is_key=True, xpath='''(//table)[1]//tr[.//a and ./td[1] <= 20]/td[last()]/text()''', type=2, regex="[^\\n\\r ,.][^\\n\\r]+"),
            Selector(task_id='Leichtathletik_Top_Performance', name="gender", is_key=False, xpath='''//meta[@property="og:url"]/@content''', type=1, regex=".+/([^/]+)/[^/]+/[^/]+"),
            Selector(task_id='Leichtathletik_Top_Performance', name="class", is_key=True, xpath='''//meta[@property="og:url"]/@content''', type=1, regex=".+/([^/]+)/[^/]+"),
            Selector(task_id='Leichtathletik_Top_Performance', name="discpiplin", is_key=True, xpath='''//meta[@property="og:url"]/@content''', type=1, regex=".+/([^/]+)/[^/]+/[^/]+/[^/]+/[^/]+"),
            Selector(task_id='Leichtathletik_Top_Performance', name="birthday", is_key=False, xpath='''(//table)[1]//tr[.//a and ./td[1] <= 20]/td[preceding-sibling::td[position()=1 and ./a]]''', type=2, regex="[^\\n\\r ,.][^\\n\\r]+"),
            Selector(task_id='Leichtathletik_Top_Performance', name="nation", is_key=False, xpath='''(//table)[1]//tr[.//a and ./td[1] <= 20]/td/img/@alt''', type=1, regex="[^\\n\\r ,.][^\\n\\r]+"),
            Selector(task_id='Leichtathletik_Top_Performance', name="area", is_key=False, xpath='''//meta[@property="og:url"]/@content''', type=1, regex=".+/([^/]+)/[^/]+/[^/]+/[^/]+"),
            Selector(task_id='Leichtathletik_Top_Performance', name="rank", is_key=False, xpath='''(//table)[1]//tr[.//a and ./td[1] <= 20]/td[1]''', type=0, regex="\\d[\\d.,]*"),

            Task(name="Leichtathletik_Top_Urls"),
            UrlSelector(task_id='Leichtathletik_Top_Urls', url="http://www.iaaf.org/records/toplists/sprints/100-metres/outdoor/men/senior", selector_task_id='Leichtathletik_Top_Urls', selector_name="", selector_name2=""),
            Selector(task_id='Leichtathletik_Top_Urls', name="url", is_key=True, xpath='''//input[@type="radio"]/@value''', type=1, regex=""),

            Task(name="Wohnungen"),
            UrlSelector(task_id='Wohnungen', url="http://www.immobilienscout24.de%s", selector_task_id='Wohnungen', selector_name="naechste_seite", selector_name2=""),
            UrlSelector(task_id='Wohnungen', url="http://www.immobilienscout24.de%s", selector_task_id='Wohnungen', selector_name="naechste_seite", selector_name2=""),
            Selector(task_id='Wohnungen', name="wohnungs_id", is_key=True, xpath='''//span[@class="title"]//a/@href''', type=0, regex="\\d[\\d.,]*"),
            Selector(task_id='Wohnungen', name="naechste_seite", is_key=False, xpath='''//span[@class="nextPageText"]/..//@href''', type=1, regex=""),

            Task(name="Wohnungsdetails"),
            UrlSelector(task_id='Wohnungsdetails', url="http://www.immobilienscout24.de/expose/%s", selector_task_id='Wohnungen', selector_name="wohnungs_id", selector_name2=""),
            Selector(task_id='Wohnungsdetails', name="wohnungs_id", is_key=True, xpath='''//a[@id="is24-ex-remember-link"]/@href''', type=0, regex="\\d[\\d.,]*"),
            Selector(task_id='Wohnungsdetails', name="postleitzahl", is_key=False, xpath='''//div[@data-qa="is24-expose-address"]//text()''', type=0, regex="\\d{5}"),
            Selector(task_id='Wohnungsdetails', name="zimmeranzahl", is_key=False, xpath='''//dd[@class="is24qa-zimmer"]//text()''', type=0, regex="\\d[\\d.,]*"),
            Selector(task_id='Wohnungsdetails', name="wohnflaeche", is_key=False, xpath='''//dd[@class="is24qa-wohnflaeche-ca"]//text()''', type=0, regex="\\d[\\d.,]*"),
            Selector(task_id='Wohnungsdetails', name="kaltmiete", is_key=False, xpath='''//dd[@class="is24qa-kaltmiete"]//text()''', type=0, regex="\\d[\\d.,]*"),
        ]

        for m in mods:
            m.save()

    def __repr__(self):
        fields = ["name"]
        fields = ", ".join(["%s=%s" % (f, repr(getattr(self, f))) for f in fields])
        return "Task(%s)" % fields

    def parse(self, html_src: str) -> 'list[Result]':
        """
        Parses an html document for a given XPath expression. Any resulting node can optionally be filtered against a regular expression

        >>> parse(html_src="<html><a> test </a></html>", selectors=[Selector(name="value", type=Selector.STRING, xpath="//text()", is_key=True)])
        [<Result: {'value': 'test'}>]
        """

        def textify(node):
            return (str(node.text) if hasattr(node, "text") else str(node)).strip()

        def merge_lists(context, *args):
            """ Merge the items of lists at same positions. If one list is shorter, its last element is repeated """
            try:
                return [" ".join([textify(arg[min(i, len(arg)-1)]) for arg in args]) for i in range(max(map(len, args)))]
            except Exception as e:
                return [""]

        def exe(context, nodes, path):
            """ Executes a given xpath with each node in the first xpath as context node """
            try:
                return [textify(node.xpath(path).pop()) if node.xpath(path) else "" for node in nodes]
            except Exception as e:
                return [""]


        ns = etree.FunctionNamespace(None)
        ns['merge_lists'] = merge_lists
        ns['exe'] = exe

        if not self.selectors.all():
            return html_src  # nothing to do

        parsed_tree = html.document_fromstring(html_src)

        selectors_results = []
        for selector in self.selectors.all():
            nodes = parsed_tree.xpath(selector.xpath)
            nodes = [textify(node) for node in nodes]

            if selector.regex:
                # Apply regex to every single node #
                selector_results = []
                for node in nodes:
                    node = str(node)
                    regex_result = re.search(selector.regex, node,  re.DOTALL | re.UNICODE)
                    if regex_result:
                        if regex_result.groups():
                            selector_results += [regex_result.groups()[-1]]
                        else:
                            selector_results += [regex_result.group()]
                    else:
                        selector_results += [None]
            else:
                selector_results = nodes

            selector_results = [selector.cast(data) for data in selector_results]  # cast to type

            selectors_results.append(selector_results)

        # convert selector results from a tuple of lists to a list of tuples #
        results = []
        for y in range(max([len(selectors_results[list(self.selectors.all()).index(key_selector)]) for key_selector in self.selectors.all() if key_selector.is_key])):  # Take as many results, as there are results for a key selector
            result = Result(task_id=self.name)
            for x, selector in enumerate(self.selectors.all()):
                selectors_results[x] = selectors_results[x] or [None]  # Guarantee that an element is there
                setattr(result, selector.name, selectors_results[x][min(y, len(selectors_results[x])-1)])

            result.key = result.get_key(self)
            if result.key:
                results.append(result)

        return results

    def login(self, url: str, user: str, password: str) -> Session:
        """
        Returns the session that is yielded by the login

        """

        session = Session()
        inputs = self.http_request(url, session=session)
        inputs[0].value = user  # TODO: more intelligent search for correct user and password field in form
        inputs[1].value = password
        data = {input.name: input.value for input in inputs}
        session.post(url, data)
        return session

    def http_request(self, url: str, session: Session=None) -> 'list[Result]':
        """
        Returns the response of an http get-request to a given url

        """
        success = False

        while not success:
            try:
                logging.error("Requested %s" % url)  # For Debugging purposes
                session = session or Session()
                html_src = session.get(url, timeout=120).text
                parsing = self.parse(html_src)
                success = True
            except Exception as e:
                logging.error(str(e))
                time.sleep(5)

        return parsing
