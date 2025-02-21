# Example Starlark build file
load("@rules_cc//cc:defs.bzl", "cc_library", "cc_binary")

cc_library(
    name = "hello_lib",
    srcs = ["hello.cc"],
    hdrs = ["hello.h"],
    visibility = ["//visibility:public"],
)

cc_binary(
    name = "hello_world",
    srcs = ["main.cc"],
    deps = [":hello_lib"],
)

def custom_rule(name, srcs):
    """Example custom rule."""
    for src in srcs:
        cc_library(
            name = name + "_" + src,
            srcs = [src],
        ) 