table_row_selector = """//table[@class = "records-table toggled-table condensedTbl"]/tr[@id]"""
task = Task(
    name="Leichtatlethik_100m_Herren",  # task name
    url="http://www.iaaf.org/records/toplists/sprints/100-metres/outdoor/men/senior",
    period=3600,  # look every 10 seconds for new
    selectors=[
        Task.Selector(name="athlete_id",   xpath=table_row_selector + "/td[4]/a/@href", type=int),
        Task.Selector(name="first_name",   xpath=table_row_selector + "/td[4]/a/text()", type=unicode),
        Task.Selector(name="last_name",    xpath=table_row_selector + "/td[4]/a/span/text()", type=unicode),
        Task.Selector(name="result_time",         xpath=table_row_selector + "/td[2]/text()", type=float),
        Task.Selector(name="competition_date",         xpath=table_row_selector + "/td[9]/text()", type=datetime.datetime),
    ],
)

def add_task():
    task.put()
    #scheduler.queue_task(Task.run_by_name, pvars=dict(name=task.name), repeats=0, period=task.period, immediate=True, retry_failed=-1)  # repeats=0 and retry_failed=-1 means indefinitely
    return db().select(db.Task.ALL)

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

def test():
    data = [tuple(selector.name for selector in task.selectors)] + task.run(store=False)
    return dict(data=data)