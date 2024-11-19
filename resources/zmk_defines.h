#define MACRO_PLACEHOLDER 0
#define ZMK_MACRO(name,...) \
name: name { \
    compatible = "zmk,behavior-macro"; \
    #binding-cells = <0>; \
    __VA_ARGS__ \
};

#define ZMK_MACRO1(name,...) \
name: name { \
    compatible = "zmk,behavior-macro-one-param"; \
    #binding-cells = <1>; \
    __VA_ARGS__ \
};

#define ZMK_MACRO2(name,...) \
name: name { \
    compatible = "zmk,behavior-macro-two-param"; \
    #binding-cells = <2>; \
    __VA_ARGS__ \
};
