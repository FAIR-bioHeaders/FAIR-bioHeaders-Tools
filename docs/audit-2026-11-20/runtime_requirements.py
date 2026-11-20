"""Print this installed toolkit's dependency closure for the dated audit.

MPL-2.0; see the repository LICENSE for historical provenance.
Run in the isolated Python 3.13 environment after installing .[jsonld].
"""

from importlib.metadata import distribution

from packaging.requirements import Requirement

seen = set()


def visit(name):
    installed = distribution(name)
    canonical = installed.metadata["Name"].lower()
    if canonical in seen:
        return
    seen.add(canonical)
    if canonical != "fair-bioheaders":
        print(f"{installed.metadata['Name']}=={installed.version}")
    for value in installed.requires or []:
        requirement = Requirement(value)
        if requirement.marker is None or any(
            requirement.marker.evaluate({"extra": extra})
            for extra in ("format", "jsonld")
        ):
            visit(requirement.name)


if __name__ == "__main__":
    visit("fair-bioheaders")
