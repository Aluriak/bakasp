
import os
import sys
import functools
from flask import Flask, request, redirect, url_for, render_template, Markup
from bakasp_backend import Backend
from config import parse_configuration_file

def populate_app_routes(app: Flask, bakasp_instances: dict, root: str = '/', uid_in_url: bool = False):
    PAGES = {
        '': Backend.html_instance_page,
        'thanks': Backend.html_thank_you_page,
        'user/<userid>': Backend.html_user_choice_page,
        'user': Backend.html_user_list_page,
    }
    CONDITIONAL_PAGES = {
        'configuration': Backend.html_config,
        'configuration/raw': Backend.html_raw_config,
        'reset': Backend.html_reset,
        'results': Backend.html_results,
        'compilation': Backend.html_compilation,
        'history': Backend.html_history,
        'overview': Backend.html_overview,
    }

    create_page_func = create_page_func_with_uid_arg if uid_in_url else create_page_func_no_uid
    create_admin_page_func = create_admin_page_func_with_uid_arg if uid_in_url else create_admin_page_func_no_uid

    for route, method in PAGES.items():
        rr = f'{root}<uid>/{route}' if uid_in_url else f'{root}{route}'
        app.route(rr)(create_page_func(route, method, bakasp_instances))
        print(f'Added {repr(rr)}')
    for route, method in CONDITIONAL_PAGES.items():
        rr = f'{root}<uid>/{route}' if uid_in_url else f'{root}{route}'
        ra = f'{root}<uid>/<admin_uid>/{route}' if uid_in_url else f'{root}<admin_uid>/{route}'
        app.route(rr)(create_page_func(route, method, bakasp_instances, True))
        app.route(ra)(create_admin_page_func(route, method, bakasp_instances))
        print(f'Added {repr(rr)}')
        print(f'Added {repr(ra)}')


def create_page_func_no_uid(*args):
    # feed first argument, uid, as None
    f = functools.partial(create_page_func_with_uid_arg(*args), None)
    f.__name__ = f.func.__name__
    return f

def create_admin_page_func_no_uid(*args):
    # feed first argument, uid, as None
    f = functools.partial(create_admin_page_func_with_uid_arg(*args), None)
    f.__name__ = f.func.__name__
    return f

def create_page_func_with_uid_arg(route, method, bakasp_instances, ensure_public: bool = False):
    def page_template(uid, *args):
        if uid not in bakasp_instances:  return redirect('/')
        if bakasp_instances[uid].haserror:  return bakasp_instances[uid].html_error_page()
        if ensure_public and route not in bakasp_instances[uid].cfg["global options"]["public pages"]:
            return redirect('/')
        return method(bakasp_instances[uid], *args)
    page_template.__name__ = f'page_{route.replace("/", "_")}'
    return page_template

def create_admin_page_func_with_uid_arg(route, method, bakasp_instances):
    def admin_page_template(uid, admin_uid, *args):
        if uid not in bakasp_instances:  return redirect('/')
        if bakasp_instances[uid].haserror:  return bakasp_instances[uid].html_error_page()
        if admin_uid != bakasp_instances[uid].admin_uid:
            return redirect('/')
        return method(bakasp_instances[uid], *args)
    admin_page_template.__name__ = f'admin_page_{route.replace("/", "_")}'
    return admin_page_template


def create_app(jsonfile: str) -> Flask or None:
    cfg, raw_cfg = parse_configuration_file(jsonfile)
    if cfg:
        template_folder = os.path.join('templates/', cfg['global options']['template'])
        app = Flask(__name__, template_folder=template_folder)
        populate_app_routes(app, {None: Backend('', '', cfg, raw_cfg)})
        return app
    else:
        return utils.create_errorlist_app(errors=raw_cfg, blueprint=blueprint)

if __name__ == "__main__":
    app = create_app(sys.argv[1])
    app.run(port=8080, debug=True)
