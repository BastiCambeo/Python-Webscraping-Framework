table_row_selector = """//table[@class = "records-table toggled-table condensedTbl"]/tr[@id]"""
task = Task(
    name="Leichthatletik_Sprint_100m_Herren",  # task name
    url="http://www.iaaf.org/records/toplists/sprints/100-metres/outdoor/men/senior",
    period=3600,  # look every hour for new data
    selectors=[
        Task.Selector(name="athlete_id",        xpath=table_row_selector + "/td[4]/a/@href", type=int),
        Task.Selector(name="first_name",        xpath=table_row_selector + "/td[4]/a/text()", type=unicode),
        Task.Selector(name="last_name",         xpath=table_row_selector + "/td[4]/a/span/text()", type=unicode),
        Task.Selector(name="result_time",       xpath=table_row_selector + "/td[2]/text()", type=float),
        Task.Selector(name="competition_date",  xpath=table_row_selector + "/td[9]/text()", type=datetime.datetime),
    ],
)

def add_task():
    task.delete_results()
    task.put()
    task.schedule()
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
    t = Task.get_by_name(task.name)
    data = [tuple(selector.name for selector in t.selectors)] + t.run(return_result=True)
    return dict(data=data)
