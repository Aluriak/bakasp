
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
    set_this_to_true_to_force_template_rendering_to_fail = False
    def on_rendering_call(template, *args, **kwargs):
        nonlocal expected_template, expected_keys
        if set_this_to_true_to_force_template_rendering_to_fail:
            assert False, "the rendering function shouldn't have been called. Did you make a backend html_* method use a template without changing the tests ?"
        assert not args, args  # should only have one positional param
        assert expected_template == template
        assert set(expected_keys) == set(kwargs)

    back = Backend('test', '', config, raw_config, render_template_func=on_rendering_call)

    FUNCTIONS_TO_RENDER_CALL = {
        back.html_instance_page: ('instance-index.html', 'admin_code,description,public_pages,remaining_instance_time,root,title'),
        back.html_thank_you_page: ('thanks.html', 'username,root'),
        back.html_user_list_page: ('user.html', 'root,user_choice_text,elements'),
        back.html_history: ('history.html', 'root,history,no_history'),
        back.html_results: ('results.html', 'root,models,header,message,footer'),
    }
    FUNCTIONS_TO_JUST_CALL = (
        back.html_config,  # won't call the template renderer, since it returns json directly
        back.html_raw_config,  # idem
        back.html_compilation,  # no template rendered too, but inlined html
        back.html_overview,  # idem
        back.html_reset,  # idem
    )
    for func, (expected_template, expected_keys) in FUNCTIONS_TO_RENDER_CALL.items():
        print(f"func={func.__name__}")
        expected_keys = set(expected_keys.split(','))
        func()  # the render function will access expected_* variables by itself

    set_this_to_true_to_force_template_rendering_to_fail = True
    for func in FUNCTIONS_TO_JUST_CALL:
        func()  # won't call the on_rendering_call
