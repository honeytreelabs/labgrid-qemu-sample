from driver.base_qemudriver import Endpoint, parse_port_forwardings


def test_parse_port_forwarding() -> None:
    assert parse_port_forwardings("""Hub -1 (net0):
  Protocol[State]    FD  Source Address  Port   Dest. Address  Port RecvQ SendQ
  TCP[ESTABLISHED]   57       127.0.0.1 56065 192.168.187.100    22     0    16
  TCP[TIME_WAIT]     53       127.0.0.1 56065 192.168.187.100    22     0     0
  TCP[HOST_FORWARD]  55       127.0.0.1 56065 192.168.187.100    22     0     0
  TCP[HOST_FORWARD]  54     example.com 46073 192.168.187.100    23     0     0
  TCP[HOST_FORWARD]  41    localhost123 38031       external.com  80     0     0
  UDP[232 sec]       56 192.168.187.100 50372  217.196.145.42   123     0     0
""") == {
        Endpoint("external.com", 80): Endpoint("localhost123", 38031),
        Endpoint("192.168.187.100", 23): Endpoint("example.com", 46073),
        Endpoint("192.168.187.100", 22): Endpoint("127.0.0.1", 56065),
    }
