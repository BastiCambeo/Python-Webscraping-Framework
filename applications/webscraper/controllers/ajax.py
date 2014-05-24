
def delete_all_tasks():
   Task.delete_all_tasks()

def add_tasks():
    for task in tasks:
        task.put()
        if task.period:
            task.schedule()

def list_tasks():
    return scheduler.tasks

def run():
    return Task.run_by_name(request.vars.name)

def delete_results():
    return Task.get_by_name(request.vars.name).delete_results()

@auth.requires_login()
def view_data():
    task = Task.get_by_name(request.vars.name)
    response.title = task.name
    data = [tuple(selector.name for selector in task.selectors)] + task.get_results()
    return dict(data=data, task=task)

def test():
    return int(string_to_float("3.00"))
