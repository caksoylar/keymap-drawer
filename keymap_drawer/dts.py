"""
Helper module to parse ZMK keymap-like DT syntax into a tree,
while keeping track of "compatible" values and utilities to parse
bindings fields.

The implementation is based on a nested expression parser for curly braces
through pyparsing with some additions on top to clean up comments and run the
C preprocessor using pcpp.
"""
import re
from itertools import chain
from io import StringIO
from collections import defaultdict

import pyparsing as pp
from pcpp.preprocessor import Preprocessor, OutputDirective, Action  # type: ignore


class DTNode:
    """Class representing a DT node with helper methods to extract fields."""

    name: str
    label: str | None
    content: str
    children: list["DTNode"]

    def __init__(self, name: str, parse: pp.ParseResults):
        """
        Initialize a node from its name (which may be in the form of `label:name`)
        and `parse` which contains the node itself.
        """

        if ":" in name:
            self.label, self.name = name.split(":", maxsplit=1)
        else:
            self.label, self.name = None, name

        self.content = " ".join(elt for elt in parse if isinstance(elt, str))
        self.children = [
            DTNode(name=elt_p, parse=elt_n)
            for elt_p, elt_n in zip(parse[:-1], parse[1:])
            if isinstance(elt_p, str) and isinstance(elt_n, pp.ParseResults)
        ]

    def get_string(self, property_re: str) -> str | None:
        """Extract value from `string` type property matching the `property_re` regex."""
        string_re = re.compile(rf'{property_re} = "(.*?)"')
        if m := string_re.search(self.content):
            return m.group(1)
        return None

    def get_array(self, property_re: str) -> list[str] | None:
        """Extract values from `array` type property matching the `property_re` regex."""
        array_re = re.compile(rf"{property_re} = <(.*?)>(, <(.*?)>)*")
        if m := array_re.search(self.content):
            fields = [m.group(1)] + [field for field in m.groups()[2:] if field is not None]
            return list(chain.from_iterable(field.split(" ") for field in fields))
        return None

    def get_phandle_array(self, property_re: str) -> list[str] | None:
        """Extract values from `phandle-array` type property matching the `property_re` regex."""
        if array_vals := self.get_array(property_re):
            return [
                f"&{stripped}"
                for binding in " ".join(array_vals).split("&")
                if (stripped := binding.strip().removeprefix("&"))
            ]
        return None


class DeviceTree:
    """
    Class that parses a DTS file (optionally preprocessed by the C preprocessor)
    and represents it as a DT tree, with some helpful methods.
    """

    _nodelabel_re = re.compile(r"([\w-]+) *: *([\w-]+) *{")
    _compatible_re = re.compile(r'compatible = "(.*?)"')
    _custom_data_header = "__keymap_drawer_data__"

    def __init__(self, in_str: str, file_name: str | None = None, preprocess: bool = True):
        """
        Given an input DTS string `in_str` and `file_name` it is read from, parse it into an internap
        tree representation and track what "compatible" value each node has.
        """
        self.raw_buffer = in_str
        self.file_name = file_name

        if preprocess:
            prepped = self._preprocess(in_str, file_name) if preprocess else in_str

        # make sure node labels and names are glued together and comments are removed,
        # then parse with nested curly braces
        self.root = DTNode(
            "ROOT",
            pp.nested_expr("{", "};")
            .ignore("//" + pp.SkipTo(pp.lineEnd))
            .ignore(pp.c_style_comment)
            .parse_string("{ " + self._nodelabel_re.sub(r"\1:\2 {", prepped) + " };")[0],
        )

        self.compatibles: defaultdict[str, list[DTNode]] = defaultdict(list)

        def assign_compatibles(node: DTNode) -> None:
            if m := self._compatible_re.search(node.content):
                self.compatibles[m.group(1)].append(node)
            for child in node.children:
                assign_compatibles(child)

        assign_compatibles(self.root)

    @staticmethod
    def _preprocess(in_str: str, file_name: str | None = None) -> str:
        def include_handler(*args):  # type: ignore
            raise OutputDirective(Action.IgnoreAndPassThrough)

        preprocessor = Preprocessor()
        preprocessor.line_directive = None
        preprocessor.on_include_not_found = include_handler
        preprocessor.parse(in_str, source=file_name)
        with StringIO() as f_out:
            preprocessor.write(f_out)
            prepped = f_out.getvalue()
        return re.sub(r"^\s*#.*?$", "", prepped)

    def get_compatible_nodes(self, compatible_value: str) -> list[DTNode]:
        """Return a list of nodes that have the given compatible value."""
        return self.compatibles[compatible_value]

    def preprocess_extra_data(self, data: str) -> str:
        """
        Given a string containing data, preprocess it in the same context as the
        original input buffer by appending the data to it and extracting the result
        afterwards.

        TODO(perf): Figure out a good interface to achieve this without running preprocessing
        twice.
        """
        in_str = self.raw_buffer + f"\n{self._custom_data_header}\n{data}"
        out = self._preprocess(in_str, self.file_name)
        data_pos = out.rfind(f"\n{self._custom_data_header}\n")
        assert data_pos >= 0, (
            f"Preprocessing extra data failed, please make sure '{self._custom_data_header}' "
            "does not get modified by #define's"
        )
        return out[data_pos + len(self._custom_data_header) + 2 :]
