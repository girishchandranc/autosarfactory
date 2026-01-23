class XmlElementDirtyTracker:
    def __init__(self):
        # Key: attribute or element; Value: True if dirty
        self.__dirty = {}
    
    def __get_key_value(self, element, attribute=None):
        return (element.get_unique_hash() + '.' + attribute) if attribute is not None else element.get_unique_hash()
    
    def __mark_element_dirty(self, element):
        while element is not None and self.is_dirty(element) is False:
            self.__dirty[self.__get_key_value(element)] = True
            # make the parent dirty
            element = element.get_parent() if hasattr(element, 'get_parent') else None

    def mark_dirty(self,element,parent,attributesToMakeDirty=[]):
        """
        Mark element and ancestors as dirty.
        element could be passed as None if it's unset/removed from the model
        """
        if element is not None and len(element.referenced_by) > 0:
            for r in element.referenced_by:
                self.__mark_element_dirty(r)

        if element is not None:
            self.__mark_element_dirty(element)
        elif element is None or parent == element.get_parent(): #to make sure that it's the right parent element we are marking as dirty. If it's referenced ones, this will be fixed by the above forloop of referenced_by
            self.__mark_element_dirty(parent)
        
        for a in attributesToMakeDirty:
            self.mark_attribute_dirty(a, element)

    def mark_attribute_dirty(self, attribute, element):
        """Mark the attribute as well as the relevant ancestors as dirty"""
        if element.get_parent() is not None:
            self.__dirty[self.__get_key_value(element, attribute)] = True
            self.__mark_element_dirty(element)

    def is_dirty(self,element) -> bool:
        return element is not None and bool(self.__dirty.get(self.__get_key_value(element), False))

    def is_attribute_dirty(self, attribute, element) -> bool:
        return bool(self.__dirty.get(self.__get_key_value(element, attribute), False))

    def clear_dirty(self):
        self.__dirty.clear()
