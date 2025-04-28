class ConfigException(Exception):
    """Exception thrown when an experiment is invalid."""

    def __init__(self, message):
        super().__init__(message)


class InvalidConfigurationException(Exception):
    """Exception thrown when experiment configuration is invalid."""

    def __init__(self, message):
        super().__init__(message)


class DefinitionNotFound(Exception):
    """Exception thrown when a definition for a provided reference does not exist."""

    def __init__(self, message):
        super().__init__(message)


class UnexpectedKeyConfigurationException(InvalidConfigurationException):
    pass


class NoStartDateException(Exception):
    def __init__(self, normandy_slug, message="Experiment has no start date."):
        super().__init__(f"{normandy_slug} -> {message}")


class NoEndDateException(Exception):
    def __init__(self, normandy_slug, message="Experiment has no end date."):
        super().__init__(f"{normandy_slug} -> {message}")
