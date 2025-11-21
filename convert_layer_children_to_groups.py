#!/usr/bin/env python3
"""
Convert Layer Children to Groups - Inkscape Extension
Converts all immediate layer children of the selected layer to regular groups.
No recursion - only processes direct layer children of the selected layer.
Converts the layers themselves to groups (doesn't create new parent groups).
"""

import inkex
from inkex import Group, Layer

class ConvertLayerChildrenToGroups(inkex.EffectExtension):

    def effect(self):
        # Get the currently selected element
        if not self.svg.selected:
            inkex.errormsg("Please select a layer first.")
            return

        # Get the first selected element (we only work with one selection)
        selected = next(iter(self.svg.selected.values()))

        # Check if the selected element is a layer
        if not isinstance(selected, Layer):
            inkex.errormsg("Please select a layer, not a regular object or group.")
            return

        # Get immediate children only (no recursion)
        children = list(selected)

        if not children:
            inkex.utils.debug("Selected layer has no children to convert.")
            return

        converted_count = 0

        for child in children:
            # Only convert child layers to groups
            if isinstance(child, Layer):
                try:
                    # Remove layer-specific attributes to convert it to a regular group
                    if child.get(inkex.addNS('groupmode', 'inkscape')) == 'layer':
                        child.attrib.pop(inkex.addNS('groupmode', 'inkscape'), None)

                    # The element is now effectively a group since it loses its layer properties
                    # but maintains all its content, transform, and other attributes

                    converted_count += 1
                    inkex.utils.debug(f"Converted layer {child.get('id')} to group")

                except Exception as e:
                    inkex.errormsg(f"Error converting layer {child.get('id')}: {str(e)}")
                    continue
            else:
                inkex.utils.debug(f"Skipping {child.get('id')} - not a layer")

        inkex.utils.debug(f"Successfully converted {converted_count} child layers to groups")

if __name__ == '__main__':
    ConvertLayerChildrenToGroups().run()
