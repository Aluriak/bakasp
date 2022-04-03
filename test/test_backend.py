
import os
from flask import Flask
from config import parse_configuration
from bakasp import create_website
from bakasp_backend import Backend


def test_basic_api():
    config, raw_config = parse_configuration({'users options': {'type': 'restricted', 'users': ('lucas', 'ada')}}, filesource=__name__)  # default config

    if config is None:
        for error in raw_config:
            print(error)
        assert config is not None, "errors were found in the configuration. See logs."

    expected_template, expected_keys = None, None
    def on_rendering_call(template, *args, **kwargs):
        nonlocal expected_template, expected_keys
        assert not args, args  # should only have one positional param
        assert expected_template == template
        assert set(expected_keys) == set(kwargs)

    back = Backend('test', '', config, raw_config, render_template_func=on_rendering_call)

    FUNCTIONS_TO_RENDER_CALL = {
        back.html_instance_page: ('instance-index.html', 'admin_code,description,public_pages,remaining_instance_time,root,title'),
        back.html_thank_you_page: ('thanks.html', 'username,root'),
        back.html_user_list_page: ('user.html', 'root,user_choice_text,elements'),
        back.html_config: ('config.html', 'root,'),
        back.html_raw_config: ('raw_config.html', 'root,'),
        back.html_config: ('config.html', 'root,'),
        back.html_compilation: ('compilation.html', 'root,'),
        back.html_history: ('history.html', 'root,history,no_history'),
        back.html_overview: ('overview.html', 'root,'),
        back.html_results: ('results.html', 'root,models,header,message,footer'),
        back.html_reset: ('reset.html', 'root,'),
    }
    for func, (expected_template, expected_keys) in FUNCTIONS_TO_RENDER_CALL.items():
        print(f"func={func.__name__}")
        expected_keys = expected_keys.split(',')
        func()  # the render function will access expected_* variables by itself


