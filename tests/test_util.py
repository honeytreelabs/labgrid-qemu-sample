import re


def test_default_network_interface() -> None:
    regex = r"""default\s+via # leading strings
                \s+\S+ # IP address
                \s+dev\s+([\w\.-]+) # interface"""

    default_route = ["default via 10.0.2.2 dev br-lan  src 10.0.2.15"]
    matches = re.findall(regex, "\n".join(default_route), re.X)
    assert matches
    assert matches[0] == "br-lan"
