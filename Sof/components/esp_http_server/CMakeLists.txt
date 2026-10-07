# Keep SDK 3.4 with local URI, parse failure and socket error fixes.
set(httpd_sdk "$ENV{IDF_PATH}/components/esp_http_server")
set(COMPONENT_ADD_INCLUDEDIRS "${httpd_sdk}/include")
set(COMPONENT_PRIV_INCLUDEDIRS "${httpd_sdk}/src"
                              "${httpd_sdk}/src/port/esp8266"
                              "${httpd_sdk}/src/util")
set(COMPONENT_SRCS "${httpd_sdk}/src/httpd_main.c"
                   "httpd_parse.c"
                   "${httpd_sdk}/src/httpd_sess.c"
                   "httpd_txrx.c"
                   "httpd_uri.c"
                   "${httpd_sdk}/src/util/ctrl_sock.c")
set(COMPONENT_PRIV_REQUIRES lwip)
set(COMPONENT_REQUIRES http_parser)
register_component()
