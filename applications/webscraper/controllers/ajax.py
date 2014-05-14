table_row_selector = """//table[@class = "records-table toggled-table condensedTbl"]/tr[@id]"""
tasks = [
    Task(
        name="Leichthatletik_Sprint_100m_Herren",  # task name
        url_generator="http://www.iaaf.org/records/toplists/sprints/100-metres/outdoor/men/senior",
        period=3600*24*30,  # look every month for new data
        selectors=[
            Task.Selector(name="athlete_id",        xpath=table_row_selector + "/td[4]/a/@href", type=int),
            Task.Selector(name="first_name",        xpath=table_row_selector + "/td[4]/a/text()", type=unicode),
            Task.Selector(name="last_name",         xpath=table_row_selector + "/td[4]/a/span/text()", type=unicode),
            Task.Selector(name="result_time",       xpath=table_row_selector + "/td[2]/text()", type=float),
            Task.Selector(name="competition_date",  xpath=table_row_selector + "/td[9]/text()", type=datetime.datetime),
        ],
    ),
    Task(
        name="Leichthatletik_Athleten",  # task name
        url_generator="[http://www.iaaf.org/athletes/athlete=%s][Leichthatletik_Sprint_100m_Herren][athlete_id]",
        period=3600*24*30,  # look every month for new data
        selectors=[
            Task.Selector(name="athlete_id",        xpath="""//meta[@property = "og:url"]/@content""", type=int),
            Task.Selector(name="name",         xpath="""//div[@class = "name-container athProfile"]/h1/text()""", type=unicode),
            Task.Selector(name="birthday",          xpath="""//div[@class = "country-date-container"]//span[4]//text()""", type=datetime.datetime),
            Task.Selector(name="country",           xpath="""//div[@class = "country-date-container"]//span[2]//text()""", type=unicode),
        ],
    )
]

def add_tasks():
    for task in tasks:
        task.put()
        task.schedule()

def delete_all_tasks():
    scheduler.terminate_process()
    Task.delete_all_results()
    db.scheduler_task.drop()
    db.scheduler_run.drop()
    db.Task.drop()

def list_tasks():
    return scheduler.tasks

def run_by_name():
    return Task.run_by_name(request.vars.name)

@auth.requires_login()
def view_data():
    task = Task.get_by_name(request.vars.name)
    response.title = task.name
    data = [tuple(selector.name for selector in task.selectors)] + task.get_results()
    return dict(data=data)

def test():
    task = tasks[0]
    data = [tuple(selector.name for selector in task.selectors)] + task.run(return_result=True, store=False)
    return dict(data=data)
