#!/usr/bin/env python3
"""
Flatten Groups and Layers - Inkscape Extension
Goes into every selected group and moves nested groups/layers to be siblings.
Processes recursively for any groups that were moved out.
Accounts for relative positioning by combining transforms.
"""

import inkex
from inkex import Group, Layer
from inkex.transforms import Transform

class FlattenGroups(inkex.EffectExtension):

    def effect(self):
        # Get the currently selected elements
        if not self.svg.selected:
            inkex.errormsg("Please select at least one group or layer.")
            return

        # We'll process all selected groups and layers
        selected_elements = list(self.svg.selected.values())

        # Keep track of all elements we need to process (including ones we move out)
        elements_to_process = []

        # First pass: collect all selected groups and layers
        for element in selected_elements:
            if isinstance(element, (Group, Layer)):
                elements_to_process.append(element)
            else:
                inkex.utils.debug(f"Skipping {element.get('id')} - not a group or layer")

        if not elements_to_process:
            inkex.errormsg("No groups or layers selected.")
            return

        total_moved = 0
        processed_ids = set()  # To avoid infinite recursion

        # Process elements (this list will grow as we move nested elements out)
        i = 0
        while i < len(elements_to_process):
            element = elements_to_process[i]
            element_id = element.get('id')

            # Skip if we've already processed this element
            if element_id in processed_ids:
                i += 1
                continue

            processed_ids.add(element_id)

            # Get the parent of current element
            parent = element.getparent()
            if parent is None:
                i += 1
                continue

            # Get immediate children that are groups or layers (NOT paths or other elements)
            container_children = []
            for child in list(element):  # Use list() to make a copy since we'll modify
                if isinstance(child, (Group, Layer)):
                    container_children.append(child)

            if not container_children:
                i += 1
                continue

            # Get ELEMENT'S transform (not parent's) - THIS IS THE FIX
            element_transform = Transform(element.get('transform')) if element.get('transform') else Transform()

            # Move each container child to be a sibling of the current element
            for child in container_children:
                try:
                    # Get child's current transform
                    child_transform = Transform(child.get('transform')) if child.get('transform') else Transform()

                    # Combine transforms: child's new transform = element_transform * child_transform
                    new_transform = element_transform @ child_transform

                    # Remove child from current element
                    element.remove(child)

                    # Set the combined transform on the child
                    if new_transform != Transform():
                        child.set('transform', str(new_transform))
                    else:
                        # Remove transform if it's identity
                        child.attrib.pop('transform', None)

                    # Insert child as sibling after the current element
                    parent.insert(parent.index(element) + 1, child)

                    # Add the moved child to our processing list so we can process it too
                    elements_to_process.append(child)

                    total_moved += 1
                    inkex.utils.debug(f"Moved {child.get('id')} out of {element_id}")
                    inkex.utils.debug(f"Combined transform: {new_transform}")

                except Exception as e:
                    inkex.errormsg(f"Error moving {child.get('id')}: {str(e)}")
                    continue

            i += 1

        inkex.utils.debug(f"Flattening complete. Moved {total_moved} groups/layers.")

if __name__ == '__main__':
    FlattenGroups().run()
