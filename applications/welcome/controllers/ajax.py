def add_task():
    task = Storage(
        name="Leichtatlethik",
        url="http://www.iaaf.org/records/toplists/sprints/100-metres/outdoor/men/senior/2013",
        xpath="""//table[@class = "records-table toggled-table condensedTbl"]/tr[@id]/td[2]/text()""",
        regex="\d+\.\d+",
        period=10
    )
    db.Task.update_or_insert(_key=dict(name=task.name), **task)
    scheduler.queue_task(run_task, pvars=dict(name=task.name), repeats=0, period=task.period, immediate=True, retry_failed=-1)
    return db().select(db.Task.ALL)

def delete_all_tasks():
    db.scheduler_task.drop()
    db.scheduler_run.drop()
    db.Task.drop()

def get_tasks():
    return scheduler.tasks

def run_task_name():
    return run_task(request.vars.name)