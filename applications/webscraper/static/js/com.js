/**
 * Created by Basti on 24.05.14.
 */

function save(reload) {
    reload = typeof reload !== 'undefined' ? reload : true;
    $.ajax({
        type: "POST",
        url: "/webscraper/ajax/save_task",
        data: $('#task_form').serialize(),
        success: function() {
            // $.web2py.flash("Successfully Saved");
            if (reload) window.location.reload();
        },
        async: false
    });
}

function query_task_status(name) {
    var intervall_handler = window.setInterval(function(){
        $.ajax({
            url:"/webscraper/ajax/get_task_status",
            type: "GET",
            dataType: "json",
            data:{name: name},
            success: function(data) {
                if (data.status != "") {
                    $.web2py.flash(data.status);
                } else {
                    window.clearInterval(intervall_handler);
                    $.web2py.hide_flash();
                }
            }
        });
    }, 5000);
}

function schedule(name) {
    save(false);
    $.ajax({
		url:"/webscraper/ajax/schedule",
		data:{name: name},
        type: "POST",
        success: function() {
            window.location.reload();
        }
    });
    setTimeout(function() { query_task_status(name);}, 5000);
}

function test(name) {
    save(false);
    $.ajax({
        type: "POST",
        url: "/webscraper/ajax/test_task",
        data: {name: name},
        dataType: "json",
        success: function(data) {
            $.web2py.flash(data.results);
        }
    });
}

function delete_results(name) {
    if (confirm('Are you sure you want to delete all results of this task? This cannot be undone!')) {
        $.ajax({
		url:"/webscraper/ajax/delete_results",
		data:{name: name},
        type: "POST",
        success: function() {
            window.location.reload();
        }
	    });
    }
}

function delete_task(name) {
    if (confirm('Are you sure you want to delete this task COMPLETELY? This cannot be undone!')) {
        $.ajax({
            url: "/webscraper/ajax/delete_task",
            type: "POST",
            data: {name: name},
            success: function () {
                window.location.href = "/";
            }
        });
    }
}

function swap_advanced() {
    /* Show Advanced elements or hide them if already shown */

    if (!window.location.hash) {
        window.location.hash = "advanced";
        $(".advanced").show();
        $("#swap_advanced").text("Simple View");
    } else {
        window.location.hash = "";
        $(".advanced").hide();
        $("#swap_advanced").text("Advanced View");
    }
}

function create_new_task() {
    /* Creates a new empty task */

    var task_name = prompt("Please enter the task name", "");

    if (task_name != null && task_name != "") {
        window.location = "/webscraper/ajax/new_task?name=" + task_name
    }
}

function update_results_properties() {
    /* When the results_id selection changes, the results_properties list must be updated */
    var results_id = $("#results_id").val();
    $.ajax({
        url:"/webscraper/ajax/get_task_selector_names",
        type: "GET",
        dataType: "json",
        data:{name: results_id},
        success: function(selector_names) {
            $("#results_properties").empty();
            for (var i in selector_names) {
                $("#results_properties").append("<option>" + selector_names[i] + "</option>")
            }
        }
    });
}

function add_url_selector() {
    $("#url_selectors").append($(".url_selector").last().clone());
}

function remove_url_selector() {
    if ($(".url_selector").length > 1)
        $(".url_selector").last().remove();
}

function add_content_selector() {
    $("#content_selectors").append($(".content_selector").last().clone());
    $("input[name=selector_is_key]").last().val(parseInt($("input[name=selector_is_key]").eq(-2).val()) + 1);
}

function remove_content_selector() {
    if ($(".content_selector").length > 1)
        $(".content_selector").last().remove();
}