table_row_selector = """//table[@class = "records-table toggled-table condensedTbl"]/tr[@id]"""
task = Task(
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
)
task2 = Task(
    name="Leichthatletik_Athleten",  # task name
    url_generator="[http://www.iaaf.org/athletes/athlete=%s][Leichthatletik_Sprint_100m_Herren][athlete_id]",
    period=3600*24*30,  # look every month for new data
    selectors=[
        Task.Selector(name="athlete_id",        xpath="""//meta[@property = "og:url"]/@content""", type=int),
        Task.Selector(name="first_name",        xpath="""//div[@class = "name-container athProfile"]/h1/text()""", type=unicode),
        Task.Selector(name="last_name",         xpath="""//div[@class = "name-container athProfile"]/h1/text()""", type=unicode, regex="\w+ ([\w\s]+\w)"),
        Task.Selector(name="birthday",          xpath="""//div[@class = "country-date-container"]//span[4]//text()""", type=datetime.datetime),
        Task.Selector(name="country",           xpath="""//div[@class = "country-date-container"]//span[2]//text()""", type=unicode),
    ],
)

def add_task():
    task2.delete_results()
    task2.put()
    task2.schedule()
    return True

def delete_all_tasks():
    scheduler.terminate_process()
    Task.delete_all_results()
    db.scheduler_task.drop()
    db.scheduler_run.drop()
    db.Task.drop()
    return True

def list_tasks():
    return scheduler.tasks

def run_by_name():
    return Task.run_by_name(request.vars.name)

@auth.requires_login()
def view_data():
    task = Task.get_by_name(request.vars.name)
    data = [tuple(selector.name for selector in task.selectors)] + task.get_results()
    return dict(data=data)

def test():
    task = task2
    t = Task.get_by_name(task.name) or task
    data = [tuple(selector.name for selector in t.selectors)] + t.run(return_result=True, store=False)
    return dict(data=data)
