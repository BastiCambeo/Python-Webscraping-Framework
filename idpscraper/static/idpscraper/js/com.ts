/**
 * Created by Basti on 24.05.14.
 */

/// <reference path="jquery.d.ts" />

function get_cookie(name) {
    var cookieValue = null;
    if (document.cookie && document.cookie != '') {
        var cookies = document.cookie.split(';');
        for (var i = 0; i < cookies.length; i++) {
            var cookie = jQuery.trim(cookies[i]);
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) == (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}
var csrftoken = get_cookie('csrftoken');
var DEFAULT = () => {};

$.ajaxSetup({
    timeout: 24*3600*1000,
    beforeSend: function(xhr, settings) {
        xhr.setRequestHeader("X-CSRFToken", csrftoken);
    }
});

function save(name, callback=DEFAULT) {
    $.ajax({
        type: "POST",
        url: "/idpscraper/save_task/" + name,
        data: $('#task_form').serialize(),
        success: callback,
        async: false
    });
}

function run(name) {
    save(name);
    $.ajax({
        type: "POST",
        url: "/idpscraper/run_task/" + name,
        success: function() {
            window.location.reload();
        }
    });
}

function export_excel(name) {
    window.location.href = "/idpscraper/export_excel/" + name + ".xlsx"
}

function test(name) {
    save(name);
    $.ajax({
        type: "GET",
        url: "/idpscraper/test_task/" + name,
        dataType: "json",
        success: function(data) {
            $.web2py.flash(data.results);
        }
    });
}

function delete_results(name) {
    if (confirm('Are you sure you want to delete all results of this task? This cannot be undone!')) {
        $.ajax({
		url:"/idpscraper/delete_results/" + name,
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
            url: "/idpscraper/delete_task/" + name,
            type: "POST",
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
        $("#swap_advanced").text("Simple View");
    } else {
        window.location.hash = "";
        $("#swap_advanced").text("Advanced View");
    }
    apply_advanced();
}

function apply_advanced() {
    /* Apply advanced or simple view respectively */

    if (!window.location.hash) {
        $(".advanced").hide();
    } else {
        $(".advanced").css( "display", "inline");
    }
}

function new_task() {
    /* Creates a new empty task */

    var task_name = prompt("Please enter the task name", "");

    if (task_name) {
        $.ajax({
            url: "/idpscraper/new_task",
            type: "POST",
            data: {
                name: task_name
            },
            dataType: "json",
            success: function() {
                window.location.href = "/idpscraper/task/" + task_name;
            }
        });
    }
}

function get_task_selectors(name, callback) {
    /* When the results_id selection changes, the results_properties list must be updated */
    $.ajax({
        url:"/idpscraper/get_task_selectors/" + name,
        type: "GET",
        dataType: "json",
        success: callback // function(task)
    });
}

function update_results_properties(url_number) {
    var task_name:string = $(".results_id").eq(url_number).val();
    get_task_selectors(task_name, selectors => {
        $(".results_properties1").eq(url_number).empty();
        $(".results_properties2").eq(url_number).empty();
        selectors.forEach((selector) => {
            $(".results_properties1").eq(url_number).append("<option>" + selector.name + "</option>");
            $(".results_properties2").eq(url_number).append("<option>" + selector.name + "</option>");
        });
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

function console_eval(command) {
    $.ajax({
        type: "POST",
        url: "/idpscraper/run_command",
        data: {command: command},
        dataType: "json",
        success: function(data) {
            $.web2py.flash(data.results);
        }
    });
}