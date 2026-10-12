# Build-local SDK overrides for DHCP reply delivery and packet summaries.
file(TO_CMAKE_PATH "$ENV{IDF_PATH}/components/lwip/apps/dhcpserver/dhcpserver.c" dhcps_original)
file(READ "${dhcps_original}" dhcps_code)
string(REPLACE "\r\n" "\n" dhcps_code "${dhcps_code}")

function(trace_dhcps_part variable old new expected)
    # Count literal matches: C source contains regex metacharacters.
    string(REPLACE "${old}" "" without "${${variable}}")
    string(LENGTH "${${variable}}" before_len)
    string(LENGTH "${without}" after_len)
    string(LENGTH "${old}" part_len)
    math(EXPR count "(${before_len} - ${after_len}) / ${part_len}")
    if(NOT count EQUAL expected)
        message(FATAL_ERROR "SDK DHCP source differs; refusing trace patch (${count}/${expected})")
    endif()
    string(REPLACE "${old}" "${new}" result "${${variable}}")
    set(${variable} "${result}" PARENT_SCOPE)
endfunction()

set(dhcps_fragment "${CMAKE_CURRENT_LIST_DIR}/dhcps_trace.inc")
trace_dhcps_part(dhcps_code "#if ESP_DHCP\n" "#if ESP_DHCP\n#include \"${dhcps_fragment}\"\n" 1)
trace_dhcps_part(dhcps_code "    m->flags = htons(BOOTP_BROADCAST);"
    "    /* Preserve the client's BOOTP broadcast flag. */" 1)
trace_dhcps_part(dhcps_code "    switch (parse_msg(pmsg_dhcps, tlen - 240)) {"
    "    dhcps_trace_save(pmsg_dhcps, dhcps_msg_cnt, p->tot_len);\n    switch (parse_msg(pmsg_dhcps, tlen - 240)) {" 1)
trace_dhcps_part(dhcps_code "udp_sendto(pcb_dhcps, p, &ip_temp, DHCPS_CLIENT_PORT)"
    "dhcps_trace_send(dhcps_netif, pcb_dhcps, p, &ip_temp, DHCPS_CLIENT_PORT, m)" 5)
trace_dhcps_part(dhcps_code "    free(pmsg_dhcps);"
    "    dhcps_trace_flush(false);\n    free(pmsg_dhcps);" 1)
trace_dhcps_part(dhcps_code "    udp_recv(pcb_dhcps, handle_dhcp, NULL);"
    "    udp_recv(pcb_dhcps, handle_dhcp, NULL);\n    dhcps_retry_reset(true);" 1)
trace_dhcps_part(dhcps_code "    if (apnetif->dhcps_pcb != NULL) {"
    "    dhcps_retry_reset(false);\n    if (apnetif->dhcps_pcb != NULL) {" 1)

set(dhcps_generated "${CMAKE_BINARY_DIR}/dhcpserver_trace.c")

# Reuse the SDK's dynamic ARP cache. Entries expire and netif cleanup removes
# them normally; no permanent/static ARP entries or new global lwIP options.
file(TO_CMAKE_PATH "$ENV{IDF_PATH}/components/lwip/lwip/src/core/ipv4/etharp.c" arp_original)
file(READ "${arp_original}" arp_code)
string(REPLACE "\r\n" "\n" arp_code "${arp_code}")
set(arp_fragment "${CMAKE_CURRENT_LIST_DIR}/dhcps_arp.inc")
set(arp_marker "#if ETHARP_SUPPORT_STATIC_ENTRIES\n/** Add a new static entry")
trace_dhcps_part(arp_code "${arp_marker}"
    "#include \"${arp_fragment}\"\n\n${arp_marker}" 1)
set(arp_generated "${CMAKE_BINARY_DIR}/etharp_dhcps.c")

# Observe the driver's asynchronous result, not just udp_sendto acceptance.
file(TO_CMAKE_PATH "$ENV{IDF_PATH}/components/lwip/port/esp8266/netif/wlanif.c" wifi_original)
file(READ "${wifi_original}" wifi_code)
string(REPLACE "\r\n" "\n" wifi_code "${wifi_code}")
set(wifi_fragment "${CMAKE_CURRENT_LIST_DIR}/dhcps_wifi.inc")
set(wifi_marker "static int low_level_send_cb(esp_aio_t* aio)\n{\n    struct pbuf* pbuf = aio->arg;")
trace_dhcps_part(wifi_code "${wifi_marker}"
    "#include \"${wifi_fragment}\"\n\n${wifi_marker}\n    dhcps_wifi_done(aio);" 1)
trace_dhcps_part(wifi_code
    "        LWIP_DEBUGF(NETIF_DEBUG, (\"low_level_output: lack memory\\n\"));"
    "        LWIP_DEBUGF(NETIF_DEBUG, (\"low_level_output: lack memory\\n\"));\n        ESP_LOGE(\"dhcps_trace\", \"wifi_drop reason=pbuf_transform\");" 1)
trace_dhcps_part(wifi_code "    err = ieee80211_output_pbuf(&aio);"
    "    struct dhcps_wifi_link link;\n    dhcps_wifi_link_save(&link, netif, p, true);\n    err = ieee80211_output_pbuf(&aio);\n    dhcps_wifi_link_log(\"tx\", &link, err);" 1)
trace_dhcps_part(wifi_code "    ethhdr = p->payload;"
    "    ethhdr = p->payload;\n    struct dhcps_wifi_link link;\n    int8_t input_error;\n    dhcps_wifi_link_save(&link, netif, p, false);" 1)
trace_dhcps_part(wifi_code "            if (netif->input(p, netif) != ERR_OK) {"
    "            input_error = netif->input(p, netif);\n            dhcps_wifi_link_log(\"rx\", &link, input_error);\n            if (input_error != ERR_OK) {" 1)
set(wifi_generated "${CMAKE_BINARY_DIR}/wlanif_dhcps.c")

idf_component_get_property(lwip_lib lwip COMPONENT_LIB)
get_target_property(lwip_sources ${lwip_lib} SOURCES)
foreach(original "${dhcps_original}" "${arp_original}" "${wifi_original}")
    list(FIND lwip_sources "${original}" source_index)
    if(source_index EQUAL -1)
        message(FATAL_ERROR "SDK DHCP/ARP/WiFi source missing; refusing reply patch")
    endif()
endforeach()
file(WRITE "${dhcps_generated}" "${dhcps_code}")
file(WRITE "${arp_generated}" "${arp_code}")
file(WRITE "${wifi_generated}" "${wifi_code}")
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
    "${dhcps_original}" "${dhcps_fragment}" "${arp_original}" "${arp_fragment}"
    "${wifi_original}" "${wifi_fragment}")
list(REMOVE_ITEM lwip_sources "${dhcps_original}" "${arp_original}" "${wifi_original}")
list(APPEND lwip_sources "${dhcps_generated}" "${arp_generated}" "${wifi_generated}")
set_property(TARGET ${lwip_lib} PROPERTY SOURCES "${lwip_sources}")
message(STATUS "DHCP OFFER/ACK honor client unicast/broadcast; dynamic ARP learning and packet summaries enabled")
message(STATUS "DHCP asynchronous WiFi TX completion summaries enabled")
message(STATUS "DHCP failed unicast uses broadcast on matching client retry; cache cleared on AP stop/start")
message(STATUS "DHCP Ethernet RX source/TX destination compared with chaddr; logs after ownership handoff")
