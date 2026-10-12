/* Included inside SDK etharp.c: reuse its ordinary expiring ARP entries. */
err_t app_dhcps_arp_learn(struct netif *netif, const ip4_addr_t *ip,
                         struct eth_addr *mac)
{
    LWIP_ASSERT_CORE_LOCKED();
    return etharp_update_arp_entry(netif, ip, mac, ETHARP_FLAG_TRY_HARD);
}
