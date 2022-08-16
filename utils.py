class UnknownDBDriverException(Exception):
    pass


def config_to_uri(
    driver: str = "sqlite",
    path: str = "keyforge_cards.sqlite",
    host: str = "localhost",
    port: int = None,
    user: str = None,
    password: str = None,
    database: str = "keyforge_decks",
) -> str:
    uri_bits = [driver, "://"]
    if driver == "sqlite":
        uri_bits.append("/")
        uri_bits.append(path)
    elif driver in ["postgresql", "mysql"]:
        if user is not None:
            uri_bits.append(user)
            if password is not None:
                uri_bits.append(":")
                uri_bits.append(password)
        uri_bits.append("@")
        uri_bits.append(host)
        if port is not None:
            uri_bits.append(":")
            uri_bits.append(port)
        uri_bits.append("/")
        uri_bits.append(database)
    else:
        raise UnknownDBDriverException(f"Unrecognized DB Driver: {driver}")
    return "".join(uri_bits)


def render_log(log: str) -> str:
    return log.message
