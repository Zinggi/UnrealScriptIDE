/**
 * Dynamic Arrays
 * ______________
 * Dynamic arrays provide various ways for reading and manipulating the content and length of the array.
 * All of these must be done through variables or struct members,
 * dynamic arrays returned from functions must be assigned to a variable first.
 *
 * Declaration: var array<type> MyArray;
 *
 * NOTE: array<bool> is not a supported type!
 *
 * Dynamic arrays now support the foreach command to allow simple iterations. The basic syntax is:
 * 	foreach ArrayVariable(out ArrayItem, optional out ItemIndex) { ... }
 * 
 * This is a non-existent class. You can't extend it.
 */
class Array
		native;

/**
 * The length of the array.
 */
var native int Length;


/**
 * Adds a item to the array.
 *
 * @param	item - The item to add.
 */
native final function AddItem( object item );

/**
 * Removes a specified item.
 *
 * @param	item - The item to remove.
 */
native final function RemoveItem( object item );

/**
 * Inserts a item at a specified index.
 *
 * @param	index - The index to insert the item at.
 * @param	count - The item to insert.
 */
native final function InsertItem( int index, object item );

/**
 * Find and returns the found element with a specified value, if nothing is found it will return -1.
 *
 * @param	value - The value to look for.
 *
 * @return	The found index or -1 if value wasn't found.
 */
native final function int Find( object  value );

/**
 * Find and returns the found element with a specified value, if nothing is found it will return -1.
 *
 * @param	propertyName - The property name of within a struct to test against.
 * @param	value - The value to look for.
 *
 * @return	The found index or -1 if value wasn't found.
 */
native final function int Find( name propertyName, object  value );

/**
 * Sorts the array.
 *
 * @param	sortDelegate - The method to use for sorting.
 */
native final function Sort( delegate sortDelegate );