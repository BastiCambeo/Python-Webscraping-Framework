""" This file contains idp specific views and calculations """

from django.shortcuts import render
from django.http import HttpResponseRedirect, HttpResponse
from idpscraper.models import Task, Selector, UrlSelector, Result, serialize
from django.core.urlresolvers import reverse
from collections import defaultdict
import datetime


def test(request):
    """ Temporary method for testing purposes """
    task = Task.get("Football_Bettina_Player_Details")

    return HttpResponse(repr(set(player.player_id for player in Task.get("Football_Bettina2_Players").results.all()) - set(player.player_id for player in Task.get("Football_Bettina2_Player_Details").results.all())))

    for player in task.results.all():
        if player.matchcount_u21 == 0 and \
                        player.matchcount_u20 == 0 and \
                        player.matchcount_u19 == 0 and \
                        player.matchcount_u18 == 0 and \
                        player.matchcount_u17 == 0 and \
                        player.matchcount_u16 == 0 and \
                        player.matchcount_u15 == 0:
            player.delete()
    return HttpResponse("finished")



    task = Task.get("Football_Bettina_Player_Details")

    # Do not forget to set the keys #
    task = Task.get("Football_Bettina_Player_Details")
    Result(task=task, results=dict(player_id=543, name="Daniel Bierofka", position="Rechtes Mittelfeld", birthday=datetime.datetime(year=1979, month=2, day=7), nation="Deutschland")).save()
    Result(task=task, results=dict(player_id=94641, name="Manuel Janzer", position="Linksaußen", birthday=datetime.datetime(year=1992, month=3, day=7), nation="Deutschland")).save()
    return HttpResponse("finished")


def relative_age_athletics(request):
    """ Illustrate the Relative Age Effect based on the athletics data """

    from collections import OrderedDict

    birthdays = OrderedDict()
    for month in ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]:
        birthdays[month] = 0

    athletes = {athlete.athlete_id: athlete for athlete in Task.get("Leichtathletik_Top_Performance").results.all()}

    for athlete in athletes.values():
        try:
            if not (athlete.birthday.day == 1 and athlete.birthday.month == 1):  # 1.1. is a dummy date for athletes where the exact birthday is unknown
                birthdays[athlete.birthday.strftime("%B")] += 1
        except:
            pass
    return render(request, 'idpscraper/relative_age.html', dict(birthdays=birthdays, considered_athlete_count=sum(birthdays.values()), athlete_count=len(athletes)))


def relative_age_football(request):
    """ Illustrate the Relative Age Effect based on the football data """
    from collections import OrderedDict

    birthdays = OrderedDict()
    for month in ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]:
        birthdays[month] = 0

    athletes = {athlete.spieler_id: athlete for athlete in Task.get("Fussball_Spieler_Details").results.all()}

    for athlete in athletes.values():
        try:
            # 1.1. is not a dummy date for players, because of the high quality of the database
            birthdays[athlete.birthday.strftime("%B")] += 1
        except:
            pass
    return render(request, 'idpscraper/relative_age.html', dict(birthdays=birthdays, considered_athlete_count=sum(birthdays.values()), athlete_count=len(athletes)))


def injuries_in_player_seasons(request):
    """ Remove all injuries and matches that are not in the season in which a player played """
    Selector.objects.update_or_create(task_id="Football_Injuries", name="season", type=Selector.INTEGER)
    Selector.objects.update_or_create(task_id="Football_Matches", name="season", type=Selector.INTEGER)

    injuries = Task.get("Football_Injuries").results.all()  # get all injuries
    matches = Task.get("Football_Matches").results.all()  # get all matches
    players = set((player.player_id, player.season) for player in Task.get("Football_Players").results.all())  # get all players with seasons

    # update injuries #
    for injury in injuries:
        injury.season = (injury.begin - datetime.timedelta(weeks=26)).year
        if (injury.player_id, injury.season) in players:
            injury.save()
        else:
            injury.delete()

    # update matches #
    for match in matches:
        match.season = (match.date - datetime.timedelta(weeks=26)).year
        if (match.player_id, match.season) in players:
            match.save()
        else:
            match.delete()

    return HttpResponse("finished")


def injuries_in_action(request):
    """ Determine if an injury occured in action:= the injury ocurred on a match day, or the day after """
    Selector.objects.update_or_create(task_id="Football_Injuries", name="in_action", type=Selector.INTEGER)
    Selector.objects.update_or_create(task_id="Football_Injuries", name="match_date", type=Selector.DATETIME)
    Selector.objects.update_or_create(task_id="Football_Matches", name="in_action", type=Selector.INTEGER)

    injuries = Task.get("Football_Injuries").results.all()  # get all injuries
    matches = defaultdict(lambda: [])
    for match in Task.get("Football_Matches").results.all():
        matches[match.player_id].append(match)
        match.in_action = 0
        match.save()
    for injury in injuries:
        injury.in_action = 0
        injury.match_date = None
        for match in matches[injury.player_id]:
            if match.date <= injury.begin <= match.date + datetime.timedelta(days=1) and match.minutes_played:
                injury.in_action = 1
                injury.match_date = match.date
                match.in_action = 1
                match.save()
                break
        injury.save()

    return HttpResponse("finished")


def injuries_synonymes(request):
    """ Calculate additional injury columns stating whether an injury has preceding / following similar injuries """

    Selector.objects.update_or_create(task_id="Football_Injuries", name="preceding_injury_date", type=Selector.DATETIME)
    Selector.objects.update_or_create(task_id="Football_Injuries", name="following_injury_date", type=Selector.DATETIME)
    Selector.objects.update_or_create(task_id="Football_Injuries", name="end_date_estimated", type=Selector.INTEGER)
    Selector.objects.update_or_create(task_id="Football_Injuries", name="preceding_injury_in_last_year", type=Selector.INTEGER)

    synonymes = """
    Außenbandanriss
    Außenbandriss
    Außenbandprobleme

    Außenbandriss Knie
    Außenbandanriss Knie

    Außenbandanriss Sprunggelenk
    Außenbandriss Sprunggelenk

    Bänderanriss
    Bänderriss
    Bänderdehnung
    Bänderverletzung

    Bänderanriss Knie
    Bänderriss Knie

    Bänderanriss Sprunggelenk
    Bänderriss Sprunggelenk
    Bänderriss in der Fußwurzel

    Innenbandabriss
    Innenbandanriss
    Innenbandriss
    Innenbandverletzung
    Innenbandzerrung

    Innenbandanriss Knie
    Innenbanddehnung Knie
    Innenbandriss Knie

    Innenbandanriss Sprunggelenk
    Innenbandriss Sprunggelenk

    Kreuzbandanriss
    Kreuzbanddehnung
    Kreuzbandriss
    Kreuzbandzerrung

    Seitenbandanriss Knie
    Seitenbandriss Knie


    Seitenbandanriss Sprunggelenk
    Seitenbandriss Sprunggelenk

    Seitenbandriss
    Seitenband-Verletzung

    Syndesmosebandanriss
    Syndesmosebandriss


    Außenmeniskuseinriss
    Meniskuseinriss
    Meniskusreizung
    Meniskusriss
    Meniskusschaden
    Meniskusverletzung

    Kapselriss
    Kapselverletzung

    Adduktorenabriss
    Adduktorenbeschwerden
    Adduktorenverletzung

    Leistenprobleme
    Leistenverletzung
    Leistenzerrung

    Muskelbündelriss
    Muskelermüdung
    Muskelfasereinriss
    Muskelfaserriss
    Muskelquetschung
    Muskelriss
    Muskelteilabriss
    Muskelverhärtung
    Muskelverletzung
    Muskelzerrung
    muskuläre Probleme

    Oberschenkelmuskelriss
    Oberschenkelprobleme
    Oberschenkelverletzung
    Oberschenkelzerrung

    Wadenmuskelriss
    Wadenzerrung

    Achillessehnenanriss
    Achillessehnenprobleme
    Achillesversenprobleme
    Achillessehnenreizung
    Achillessehnenriss

    Sehnenanriss
    Sehnenentzündung
    Sehnenreizung
    Sehnenriss

    Patellarsehnenanriss
    Patellarsehnenprobleme
    Patellarsehnenreizung
    Patellarsehnenriss
    """.split("\n")

    # Group synonyme injury descriptions #
    grouped_injuries = dict()
    group = 0
    for description in synonymes:
        description = description.strip().lower()
        if not description:
            group += 1
        else:
            grouped_injuries[description] = group

    # caluclate preceding and following injury date columns #
    injuries_by_player = defaultdict(lambda: [])
    for injury in sorted(Task.get("Football_Injuries").results.all(), key=lambda i: i.begin):  # get all injuries sorted by begin
        injury.following_injury_date = None
        injury.preceding_injury_date = None
        injury.end_date_estimated = int(not injury.end or injury.end >= datetime.datetime.now())
        injury.preceding_injury_in_last_year = 0  # := False
        injuries_by_player[injury.player_id].append(injury)

    for player_id, injuries in injuries_by_player.items():
        for i, injury1 in enumerate(injuries):
            for injury2 in injuries[i + 1:]:
                if grouped_injuries.get(injury1.description.strip().lower(), injury1.description.strip().lower()) == \
                        grouped_injuries.get(injury2.description.strip().lower(), injury2.description.strip().lower()):
                    # first following similar injury found #
                    injury1.following_injury_date = injury2.begin
                    injury2.preceding_injury_date = injury1.begin
                    injury2.preceding_injury_in_last_year = int((injury2.begin - injury2.preceding_injury_date).days < 365)
                    break
            injury1.save()

    return HttpResponse("finished")


def injuries_per_day(request):
    """ Unfold injury data per day. Example: An injury lasting 7 days becomes 7 rows """
    return repr([dict(id=injury.player_id, begin=injury.begin, end=injury.end) for injury in Task.get("Fussball_Verletzungen").results.all() if injury.begin])


def calculate_bettina_columns(request):
    """ Adds debuts and playing minutes to bettinas player_details """

    player_details_task_id = "Football_Bettina2_Player_Details"
    player_matches_task_id = "Football_Bettina2_Matches"

    Selector.objects.update_or_create(task_id=player_details_task_id, name="matchcount_A", type=Selector.INTEGER)
    Selector.objects.update_or_create(task_id=player_details_task_id, name="matchcount_u21", type=Selector.INTEGER)
    Selector.objects.update_or_create(task_id=player_details_task_id, name="matchcount_u20", type=Selector.INTEGER)
    Selector.objects.update_or_create(task_id=player_details_task_id, name="matchcount_u19", type=Selector.INTEGER)
    Selector.objects.update_or_create(task_id=player_details_task_id, name="matchcount_u18", type=Selector.INTEGER)
    Selector.objects.update_or_create(task_id=player_details_task_id, name="matchcount_u17", type=Selector.INTEGER)
    Selector.objects.update_or_create(task_id=player_details_task_id, name="matchcount_u16", type=Selector.INTEGER)
    Selector.objects.update_or_create(task_id=player_details_task_id, name="matchcount_u15", type=Selector.INTEGER)
    Selector.objects.update_or_create(task_id=player_details_task_id, name="minutes_first_BL_season", type=Selector.INTEGER)
    Selector.objects.update_or_create(task_id=player_details_task_id, name="debut_date_first_BL_season", type=Selector.DATETIME)
    Selector.objects.update_or_create(task_id=player_details_task_id, name="debut_club_first_BL_season", type=Selector.STRING)
    Selector.objects.update_or_create(task_id=player_details_task_id, name="minutes_age_24", type=Selector.INTEGER)

    def season_from_date(d):
        if not d:
            return d
        return (d - datetime.timedelta(days=365 / 2)).year

    # Create Player dictionary
    players = dict()
    for player in Task.get(player_details_task_id).results.all():
        players[player.player_id] = player
        player.matchcount_A = 0
        player.matchcount_u21 = 0
        player.matchcount_u20 = 0
        player.matchcount_u19 = 0
        player.matchcount_u18 = 0
        player.matchcount_u17 = 0
        player.matchcount_u16 = 0
        player.matchcount_u15 = 0
        player.minutes_first_BL_season = 0
        player.debut_date_first_BL_season = None
        player.debut_club_first_BL_season = None
        player.minutes_age_24 = 0

    # Fill Data
    for match in Task.get(player_matches_task_id).results.all():
        if not match.minutes_played: continue

        player = players[match.player_id]
        if match.club == "Deutschland":
            player.matchcount_A += 1
        elif match.club == "Deutschland U21":
            player.matchcount_u21 += 1
        elif match.club == "Deutschland U20":
            player.matchcount_u20 += 1
        elif match.club == "Deutschland U19":
            player.matchcount_u19 += 1
        elif match.club == "Deutschland U18":
            player.matchcount_u18 += 1
        elif match.club == "Deutschland U17":
            player.matchcount_u17 += 1
        elif match.club == "Deutschland U16":
            player.matchcount_u16 += 1
        elif match.club == "Deutschland U15":
            player.matchcount_u15 += 1
        elif match.league == "1.Bundesliga":
            if not player.debut_date_first_BL_season or match.date < player.debut_date_first_BL_season:
                player.debut_date_first_BL_season = match.date
                player.debut_club_first_BL_season = match.club

            if season_from_date(player.birthday + datetime.timedelta(days=int(24 * 365.25))) == season_from_date(match.date):
                player.minutes_age_24 += match.minutes_played

    for match in Task.get(player_matches_task_id).results.all():
        if not match.minutes_played: continue
        player = players[match.player_id]
        if match.league == "1.Bundesliga" and season_from_date(match.date) == season_from_date(player.debut_date_first_BL_season):
            player.minutes_first_BL_season += match.minutes_played

    # save
    for player_id, player in players.items():
        player.save()
    return HttpResponse("finished")


def put_tasks(request):
    """ Initialize the database with the tasks from the IDP. Attention: All other tasks will be deleted! """
    UrlSelector.objects.all().delete()
    Selector.objects.all().delete()

    mods = [
        Task(name="Football_Seasons"),
        UrlSelector(task_id='Football_Seasons', url="http://www.transfermarkt.de/3262/kader/verein/3262/", selector_task_id='Football_Seasons', selector_name="season", selector_name2="season"),
        Selector(task_id='Football_Seasons', name="season", is_key=True, xpath='''//select[@name="saison_id"]/option/@value''', type=0, regex="200[89]|201\\d"),

        Task(name="Football_Clubs"),
        UrlSelector(task_id='Football_Clubs', url="http://www.transfermarkt.de/1-bundesliga/startseite/wettbewerb/L1/saison_id/%s", selector_task_id='Football_Seasons', selector_name="season", selector_name2="season"),
        Selector(task_id='Football_Clubs', name="url", is_key=True, xpath='''//table[@class='items']//tr/td[@class='hauptlink no-border-links']/a[1]/@href''', type=1, regex="[^\\n\\r ,.][^\\n\\r]+"),

        Task(name="Football_Players"),
        UrlSelector(task_id='Football_Players', url="http://www.transfermarkt.de/%s", selector_task_id='Football_Clubs', selector_name="url", selector_name2="url"),
        Selector(task_id='Football_Players', name="player_id", is_key=True, xpath='''//a[@class="spielprofil_tooltip"]/@href''', type=0, regex="\\d[\\d.,]*"),
        Selector(task_id='Football_Players', name="season", is_key=True, xpath='''//select[@name="saison_id"]/option[@selected="selected"]/@value''', type=0, regex="\\d[\\d.,]*"),

        Task(name="Football_Matches"),
        UrlSelector(task_id='Football_Matches', url="http://www.transfermarkt.de/spieler/leistungsdatendetails/spieler/%s/plus/1/saison/%s", selector_task_id='Football_Players', selector_name="player_id", selector_name2="season"),
        Selector(task_id='Football_Matches', name="player_id", is_key=True, xpath='''(//a[@class="megamenu"])[1]/@href''', type=0, regex="\\d[\\d.,]*"),
        Selector(task_id='Football_Matches', name="date", is_key=True, xpath='''//div[@class="responsive-table"]/table//tr/td[2]''', type=2, regex="[^\\n\\r ,.][^\\n\\r]+"),
        Selector(task_id='Football_Matches', name="minutes_played", is_key=False, xpath='''//div[@class="responsive-table"]/table//tr/td[2]/following-sibling::*[last()]''', type=0, regex="\\d[\\d.,]*"),

        Task(name="Football_Player_Details"),
        UrlSelector(task_id='Football_Player_Details', url="http://www.transfermarkt.de/daten/profil/spieler/%s", selector_task_id='Football_Players', selector_name="player_id", selector_name2="player_id"),
        Selector(task_id='Football_Player_Details', name="player_id", is_key=True, xpath='''//link[@rel="canonical"]/@href''', type=0, regex="\\d[\\d.,]*"),
        Selector(task_id='Football_Player_Details', name="name", is_key=False, xpath='''//div[@class="spielername-profil"]/text()''', type=1, regex="[^\\n\\r ,.][^\\n\\r]+"),
        Selector(task_id='Football_Player_Details', name="position", is_key=False, xpath='''//table[@class="profilheader"]//td[preceding-sibling::th/text()="Position:"]''', type=1, regex="[^\\n\\r ,.][^\\n\\r]+"),
        Selector(task_id='Football_Player_Details', name="birthday", is_key=False, xpath='''//td[preceding-sibling::th/text()="Geburtsdatum:"]/a/text()''', type=2, regex="[^\\n\\r ,.][^\\n\\r]+"),
        Selector(task_id='Football_Player_Details', name="size", is_key=False, xpath='''//td[preceding-sibling::th/text()="Größe:"]//text()''', type=3, regex="\\d[\\d.,:]*"),
        Selector(task_id='Football_Player_Details', name="retire_date", is_key=False, xpath='''//table[@class="profilheader"]//td[preceding-sibling::*[.//@title="Karriereende"]]''', type=2, regex="[^\\n\\r ,.][^\\n\\r]+"),

        Task(name="Football_Transfers"),
        UrlSelector(task_id='Football_Transfers', url="http://www.transfermarkt.de/daten/profil/spieler/%s", selector_task_id='Football_Players', selector_name="player_id", selector_name2="player_id"),
        Selector(task_id='Football_Transfers', name="player_id", is_key=True, xpath='''(//a[@class="megamenu"])[1]/@href''', type=0, regex="\\d[\\d.,]*"),
        Selector(task_id='Football_Transfers', name="date", is_key=False, xpath='''(//table)[3]//tr/td[2]//text()''', type=2, regex="[^\\n\\r ,.][^\\n\\r]+"),
        Selector(task_id='Football_Transfers', name="begin", is_key=True, xpath='''(//table)[3]//tr/td[5]/a/text()''', type=1, regex="[^\\n\\r ,.][^\\n\\r]+"),
        Selector(task_id='Football_Transfers', name="end", is_key=True, xpath='''(//table)[3]//tr/td[8]/a/text()''', type=1, regex="[^\\n\\r ,.][^\\n\\r]+"),

        Task(name="Football_Injuries"),
        UrlSelector(task_id='Football_Injuries', url="http://www.transfermarkt.de/spieler/verletzungen/spieler/%s", selector_task_id='Football_Players', selector_name="player_id", selector_name2="player_id"),
        UrlSelector(task_id='Football_Injuries', url="http://www.transfermarkt.de%s", selector_task_id='Football_Injuries', selector_name="next_url", selector_name2="player_id"),
        Selector(task_id='Football_Injuries', name="player_id", is_key=True, xpath='''(//a[@class="megamenu"])[1]/@href''', type=0, regex="\\d[\\d.,]*"),
        Selector(task_id='Football_Injuries', name="description", is_key=False, xpath='''//table[@class="items"]//tr/td[2]/text()''', type=1, regex="[^\\n\\r ,.][^\\n\\r]+"),
        Selector(task_id='Football_Injuries', name="begin", is_key=True, xpath='''//table[@class="items"]//tr/td[3]/text()''', type=2, regex="[^\\n\\r ,.][^\\n\\r]+"),
        Selector(task_id='Football_Injuries', name="end", is_key=False, xpath='''//table[@class="items"]//tr/td[4]/text()''', type=2, regex="[^\\n\\r ,.][^\\n\\r]+"),
        Selector(task_id='Football_Injuries', name="duration", is_key=False, xpath='''//table[@class="items"]//tr/td[5]/text()''', type=0, regex="\\d[\\d.,]*"),
        Selector(task_id='Football_Injuries', name="missed_games", is_key=False, xpath='''//table[@class="items"]//tr/td[6]/text()''', type=0, regex="\\d[\\d.,]*"),
        Selector(task_id='Football_Injuries', name="club", is_key=False, xpath='''exe(//table[@class="items"]//tr/td[6],".//@title")''', type=1, regex="[^\\n\\r ,.][^\\n\\r]+"),
        Selector(task_id='Football_Injuries', name="next_url", is_key=False, xpath='''//li[@class="naechste-seite"]/a/@href''', type=1, regex="[^\\n\\r ,.][^\\n\\r]+"),

        Task(name="Football_Bettina_Seasons"),
        UrlSelector(task_id='Football_Bettina_Seasons', url="http://www.transfermarkt.de/3262/kader/verein/3262/", selector_task_id='Football_Bettina_Seasons', selector_name="season", selector_name2="season"),
        Selector(task_id='Football_Bettina_Seasons', name="season", is_key=True, xpath='''//select[@name="saison_id"]/option/@value''', type=0, regex="200[1-9]|201\\d"),

        Task(name='Football_Bettina_Players'),
        Selector(task_id='Football_Bettina_Players', name='player_id', type=0, xpath='//a[@class="spielprofil_tooltip"]/@href', regex='\\d[\\d.,]*', is_key=True),
        UrlSelector(task_id='Football_Bettina_Players', url='http://www.transfermarkt.de/deutschland-u21/startseite/verein/3817/saison_id/%s', selector_task_id='Football_Bettina_Seasons', selector_name='season', selector_name2='season'),
        UrlSelector(task_id='Football_Bettina_Players', url='http://www.transfermarkt.de/deutschland-u20/startseite/verein/5709/saison_id/%s', selector_task_id='Football_Bettina_Seasons', selector_name='season', selector_name2='season'),
        UrlSelector(task_id='Football_Bettina_Players', url='http://www.transfermarkt.de/deutschland-u19/startseite/verein/5710/saison_id/%s', selector_task_id='Football_Bettina_Seasons', selector_name='season', selector_name2='season'),
        UrlSelector(task_id='Football_Bettina_Players', url='http://www.transfermarkt.de/deutschland-u18/startseite/verein/9067/saison_id/%s', selector_task_id='Football_Bettina_Seasons', selector_name='season', selector_name2='season'),
        UrlSelector(task_id='Football_Bettina_Players', url='http://www.transfermarkt.de/deutschland-u17/startseite/verein/17662/saison_id/%s', selector_task_id='Football_Bettina_Seasons', selector_name='season', selector_name2='season'),
        UrlSelector(task_id='Football_Bettina_Players', url='http://www.transfermarkt.de/deutschland-u16/startseite/verein/17368/saison_id/%s', selector_task_id='Football_Bettina_Seasons', selector_name='season', selector_name2='season'),
        UrlSelector(task_id='Football_Bettina_Players', url='http://www.transfermarkt.de/deutschland-u15/startseite/verein/27300/saison_id/%s', selector_task_id='Football_Bettina_Seasons', selector_name='season', selector_name2='season'),

        Task(name='Football_Bettina_Player_Seasons'),
        UrlSelector(task_id='Football_Bettina_Player_Seasons', url='http://www.transfermarkt.de/player/leistungsdaten/spieler/%s/plus/?saison=1900', selector_task_id='Football_Bettina_Players', selector_name='player_id', selector_name2='player_id'),
        Selector(task_id='Football_Bettina_Player_Seasons', name='player_id', type=0, xpath='''(//a[@class="megamenu"])[1]/@href''', regex='\\d[\\d.,]*', is_key=True),
        Selector(task_id='Football_Bettina_Player_Seasons', name="season", is_key=True, xpath='''//select[@name="saison"]/option/@value''', type=0),

        Task(name="Football_Bettina_Matches"),
        UrlSelector(task_id='Football_Bettina_Matches', url="http://www.transfermarkt.de/spieler/leistungsdatendetails/spieler/%s/plus/1/saison/%s", selector_task_id='Football_Bettina_Player_Seasons', selector_name="player_id", selector_name2="season"),
        Selector(task_id='Football_Bettina_Matches', name="player_id", is_key=True, xpath='''(//a[@class="megamenu"])[1]/@href''', type=0, regex="\\d[\\d.,]*"),
        Selector(task_id='Football_Bettina_Matches', name="date", is_key=True, xpath='''//div[@class="responsive-table"]/table//tr/td[2]''', type=2, regex="[^\\n\\r ,.][^\\n\\r]+"),
        Selector(task_id='Football_Bettina_Matches', name="minutes_played", is_key=False, xpath='''//div[@class="responsive-table"]/table//tr/td[2]/following-sibling::*[last()]''', type=0, regex="\\d[\\d.,]*"),
        Selector(task_id='Football_Bettina_Matches', name='club', type=1, xpath='//div[@class="responsive-table"]/table//tr/td[@class="no-border-links "]/a/@title', regex='[^\\n\\r ,.][^\\n\\r]+', is_key=False),
        Selector(task_id='Football_Bettina_Matches', name='league', type=1, xpath='exe(//div[@class="responsive-table"]/table//tr/td[2], \'ancestor::div[@class="responsive-table"]/div/text()\')', regex='[^\\n\\r ,.][^\\n\\r]+', is_key=False),

        Task(name='Football_Bettina_Player_Details'),
        Selector(task_id='Football_Bettina_Player_Details', name='player_id', type=0, xpath='//link[@rel="canonical"]/@href', regex='\\d[\\d.,]*', is_key=True),
        Selector(task_id='Football_Bettina_Player_Details', name='name', type=1, xpath='//div[@class="spielername-profil"]/text()', regex='[^\\n\\r ,.][^\\n\\r]+', is_key=False),
        Selector(task_id='Football_Bettina_Player_Details', name='position', type=1, xpath='//table[@class="profilheader"]//td[preceding-sibling::th/text()="Position:"]', regex='[^\\n\\r ,.][^\\n\\r]+', is_key=False),
        Selector(task_id='Football_Bettina_Player_Details', name='birthday', type=2, xpath='//td[preceding-sibling::th/text()="Geburtsdatum:"]/a/text()', regex='[^\\n\\r ,.][^\\n\\r]+', is_key=False),
        UrlSelector(task_id='Football_Bettina_Player_Details', url='http://www.transfermarkt.de/daten/profil/spieler/%s', selector_task_id='Football_Bettina_Players', selector_name='player_id', selector_name2='player_id'),

        Task(name="Football_Bettina2_Clubs"),
        UrlSelector(task_id='Football_Bettina2_Clubs', url="http://www.transfermarkt.de/1-bundesliga/startseite/wettbewerb/L1/saison_id/%s", selector_task_id='Football_Bettina_Seasons', selector_name="season", selector_name2="season"),
        Selector(task_id='Football_Bettina2_Clubs', name="url", is_key=True, xpath='''//table[@class='items']//tr/td[@class='hauptlink no-border-links']/a[1]/@href''', type=1, regex="[^\\n\\r ,.][^\\n\\r]+"),

        Task(name="Football_Bettina2_Players"),
        UrlSelector(task_id='Football_Bettina2_Players', url="http://www.transfermarkt.de/%s", selector_task_id='Football_Bettina2_Clubs', selector_name="url", selector_name2="url"),
        Selector(task_id='Football_Bettina2_Players', name="player_id", is_key=True, xpath='''//a[@class="spielprofil_tooltip"]/@href''', type=0, regex="\\d[\\d.,]*"),
        Selector(task_id='Football_Bettina2_Players', name="season", is_key=True, xpath='''//select[@name="saison_id"]/option[@selected="selected"]/@value''', type=0, regex="\\d[\\d.,]*"),
        Selector(task_id='Football_Bettina2_Players', name="age", is_key=True, xpath='''(//table[@class="items"]//tr)//td[3]//text()''', type=0, regex="\((24)\)"),

        Task(name='Football_Bettina2_Player_Seasons'),
        UrlSelector(task_id='Football_Bettina2_Player_Seasons', url='http://www.transfermarkt.de/player/leistungsdaten/spieler/%s/plus/?saison=1900', selector_task_id='Football_Bettina2_Players', selector_name='player_id', selector_name2='player_id'),
        Selector(task_id='Football_Bettina2_Player_Seasons', name='player_id', type=0, xpath='''(//a[@class="megamenu"])[1]/@href''', regex='\\d[\\d.,]*', is_key=True),
        Selector(task_id='Football_Bettina2_Player_Seasons', name="season", is_key=True, xpath='''//select[@name="saison"]/option/@value''', type=0),

        Task(name="Football_Bettina2_Matches"),
        UrlSelector(task_id='Football_Bettina2_Matches', url="http://www.transfermarkt.de/spieler/leistungsdatendetails/spieler/%s/plus/1/saison/%s", selector_task_id='Football_Bettina2_Player_Seasons', selector_name="player_id", selector_name2="season"),
        Selector(task_id='Football_Bettina2_Matches', name="player_id", is_key=True, xpath='''(//a[@class="megamenu"])[1]/@href''', type=0, regex="\\d[\\d.,]*"),
        Selector(task_id='Football_Bettina2_Matches', name="date", is_key=True, xpath='''//div[@class="responsive-table"]/table//tr/td[2]''', type=2, regex="[^\\n\\r ,.][^\\n\\r]+"),
        Selector(task_id='Football_Bettina2_Matches', name="minutes_played", is_key=False, xpath='''//div[@class="responsive-table"]/table//tr/td[2]/following-sibling::*[last()]''', type=0, regex="\\d[\\d.,]*"),
        Selector(task_id='Football_Bettina2_Matches', name='club', type=1, xpath='//div[@class="responsive-table"]/table//tr/td[@class="no-border-links "]/a/@title', regex='[^\\n\\r ,.][^\\n\\r]+', is_key=False),
        Selector(task_id='Football_Bettina2_Matches', name='league', type=1, xpath='exe(//div[@class="responsive-table"]/table//tr/td[2], \'ancestor::div[@class="responsive-table"]/div/text()\')', regex='[^\\n\\r ,.][^\\n\\r]+', is_key=False),

        Task(name='Football_Bettina2_Player_Details'),
        Selector(task_id='Football_Bettina2_Player_Details', name='player_id', type=0, xpath='//link[@rel="canonical"]/@href', regex='\\d[\\d.,]*', is_key=True),
        Selector(task_id='Football_Bettina2_Player_Details', name='name', type=1, xpath='//div[@class="spielername-profil"]/text()', regex='[^\\n\\r ,.][^\\n\\r]+', is_key=False),
        Selector(task_id='Football_Bettina2_Player_Details', name='position', type=1, xpath='//table[@class="profilheader"]//td[preceding-sibling::th/text()="Position:"]', regex='[^\\n\\r ,.][^\\n\\r]+', is_key=False),
        Selector(task_id='Football_Bettina2_Player_Details', name='birthday', type=2, xpath='//td[preceding-sibling::th/text()="Geburtsdatum:"]/a/text()', regex='[^\\n\\r ,.][^\\n\\r]+', is_key=False),
        UrlSelector(task_id='Football_Bettina2_Player_Details', url='http://www.transfermarkt.de/daten/profil/spieler/%s', selector_task_id='Football_Bettina2_Players', selector_name='player_id', selector_name2='player_id'),

        Task(name='Leichtathletik_Saisons'),
        Selector(task_id='Leichtathletik_Saisons', name='saison', type=0, xpath="id('selectyear')/option/@value", regex='\\d\\d\\d\\d', is_key=True),
        UrlSelector(task_id='Leichtathletik_Saisons', url='http://www.iaaf.org/results', selector_task_id='Leichtathletik_Saisons', selector_name='', selector_name2=''),

        Task(name="Leichtathletik_Disziplinen"),
        UrlSelector(task_id='Leichtathletik_Disziplinen', url="http://www.iaaf.org/athletes", selector_task_id='Leichtathletik_Disziplinen', selector_name="disciplin", selector_name2=""),
        Selector(task_id='Leichtathletik_Disziplinen', name="disciplin", is_key=True, xpath='''//select[@id="selectDiscipline"]/option/@value''', type=1, regex=""),

        Task(name="Leichtathletik_Athleten"),
        UrlSelector(task_id='Leichtathletik_Athleten', url="http://www.iaaf.org/athletes/search?name=&country=&discipline=%s&gender=", selector_task_id='Leichtathletik_Disziplinen', selector_name="disciplin", selector_name2=""),
        Selector(task_id='Leichtathletik_Athleten', name="athlete_id", is_key=True, xpath='''//table[@class="records-table"]//tr[not(@class)]/td[1]//@href''', type=0, regex="\\d[\\d.,]*"),
        Selector(task_id='Leichtathletik_Athleten', name="first_name", is_key=False, xpath='''//table[@class="records-table"]//tr[not(@class)]/td[1]//a/text()''', type=1, regex="[^\\n\\r ,.][^\\n\\r]+"),
        Selector(task_id='Leichtathletik_Athleten', name="last_name", is_key=False, xpath='''//table[@class="records-table"]//tr[not(@class)]/td[1]/a/span/text()''', type=1, regex="[^\\n\\r ,.][^\\n\\r]+"),
        Selector(task_id='Leichtathletik_Athleten', name="sex", is_key=False, xpath='''//table[@class="records-table"]//tr[not(@class)]/td[2]/text()''', type=1, regex="[^\\n\\r ,.][^\\n\\r]+"),
        Selector(task_id='Leichtathletik_Athleten', name="country", is_key=False, xpath='''//table[@class="records-table"]//tr[not(@class)]/td[3]/text()''', type=1, regex="[^\\n\\r ,.][^\\n\\r]+"),
        Selector(task_id='Leichtathletik_Athleten', name="birthday", is_key=False, xpath='''//table[@class="records-table"]//tr[not(@class)]/td[4]/text()''', type=2, regex="[^\\n\\r ,.][^\\n\\r]+"),

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

        Task(name="Leichtathletik_Top_Urls"),
        UrlSelector(task_id='Leichtathletik_Top_Urls', url="http://www.iaaf.org/records/toplists/sprints/100-metres/outdoor/men/senior", selector_task_id='Leichtathletik_Top_Urls', selector_name="", selector_name2=""),
        Selector(task_id='Leichtathletik_Top_Urls', name="url", is_key=True, xpath='''//input[@type="radio"]/@value''', type=1, regex=""),

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

        Task(name='Wohnungen'),
        Selector(task_id='Wohnungen', name='wohnungs_id', type=0, xpath='//span[@class="title"]//a/@href', regex='\\d[\\d.,]*', is_key=True),
        Selector(task_id='Wohnungen', name='naechste_seite', type=1, xpath='//span[@class="nextPageText"]/..//@href', regex='[^\\n\\r ,.][^\\n\\r]+', is_key=False),
        UrlSelector(task_id='Wohnungen', url='http://www.immobilienscout24.de/Suche/S-2/Wohnung-Miete/Fahrzeitsuche/M_fcnchen/-/116301/2030629/-/-/20/1,50-/30,00-/EURO--900,00/-/-/-/-/-/-/-/-/-/-/-/-/true', selector_task_id='Wohnungen', selector_name='naechste_seite', selector_name2='wohnungs_id'),
        UrlSelector(task_id='Wohnungen', url='http://www.immobilienscout24.de%s', selector_task_id='Wohnungen', selector_name='naechste_seite', selector_name2='wohnungs_id'),

        Task(name='Wohnungsdetails'),
        Selector(task_id='Wohnungsdetails', name='wohnungs_id', type=0, xpath='//a[@id="is24-ex-remember-link"]/@href', regex='\\d[\\d.,]*', is_key=True),
        Selector(task_id='Wohnungsdetails', name='gesamtmiete', type=3, xpath='//strong[@class="is24qa-gesamtmiete"]/text()[2]', regex='\\d[\\d.,:]*', is_key=False),
        Selector(task_id='Wohnungsdetails', name='zimmeranzahl', type=3, xpath='//dd[@class="is24qa-zimmer"]//text()', regex='\\d[\\d.,:]*', is_key=False),
        Selector(task_id='Wohnungsdetails', name='wohnflaeche', type=0, xpath='//dd[@class="is24qa-wohnflaeche-ca"]//text()', regex='\\d[\\d.,]*', is_key=False),
        Selector(task_id='Wohnungsdetails', name='kaltmiete', type=0, xpath='//dd[@class="is24qa-kaltmiete"]/text()[2]', regex='\\d[\\d.,]*', is_key=False),
        Selector(task_id='Wohnungsdetails', name='addresse', type=1, xpath='all(//div[@data-qa="is24-expose-address"]//text())', regex='(.*)Karte', is_key=False),
        UrlSelector(task_id='Wohnungsdetails', url='http://www.immobilienscout24.de/expose/%s', selector_task_id='Wohnungen', selector_name='wohnungs_id', selector_name2='wohnungs_id'),
    ]

    for m in mods:
        m.save()

    return HttpResponseRedirect(reverse("idpscraper:index"))