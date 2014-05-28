/**
 * Created by Basti on 24.05.14.
 */

function run(name) {
    $.ajax({
		url:"/ajax/run",
		data:{name: name},
        type: "POST",
        success: function() {
            window.location.reload();
        },
        error: function(xhr, status, error)
        {
        	window.location.href = "http://localhost/admin/default/errors/webscraper";
        }
	});
}

function delete_results(name) {
    $.ajax({
		url:"/ajax/delete_results",
		data:{name: name},
        type: "POST",
        success: function() {
            window.location.reload();
        },
        error: function(xhr, status, error)
        {
        	window.location.href = "http://localhost/admin/default/errors/webscraper";
        }
	});
}

function reload_tasks(name) {
    $.ajax({
		url:"/ajax/add_tasks",
        type: "POST",
        success: function() {
            window.location.reload();
        },
        error: function(xhr, status, error)
        {
        	window.location.href = "http://localhost/admin/default/errors/webscraper";
        }
	});
}

function delete_task(name) {
    $.ajax({
		url:"/ajax/delete_task",
        type: "POST",
        data:{name: name},
        success: function() {
            window.location.href = "/";
        },
        error: function(xhr, status, error)
        {
        	window.location.href = "http://localhost/admin/default/errors/webscraper";
        }
	});
}