/**
 * HiddenFunctions
 * ______________
 *
 * All stuff that is somehow a hidden UnrealScript feature.
 * 
 * This is a non-existent class. You can't extend it.
 */
class HiddenFunctions
		native;

/**
 * Creates a new vector with the given components.
 */
native function vector vect( float X, float Y, float Z );

/**
 * Creates a new rotator with the given components.
 */
native function rotator rot( int Pitch, int Yaw, int Roll );


/**
 * Creates a new Object of the given class.
 * For Actors, you must use the Spawn function!
 *
 * The actual syntax for the new operator is as follows: 
 * 		ObjectVar = new[(InOuter, InName, InFlags)] <class'InClass'>[(InTemplate)];
 * E.g:
 * 		NewObj = new class'Engine.LightFunction';
 * 		NewObj = new(None,'NewLight') class'Engine.LightFunction' (LightFunctionTemplate);
 *
 * @param		InOuter			(optional) the object to assign as the Outer for the newly created object.
 *                              If not specified, the object's Outer will be set to a special package which exists only while the game is running, called the "transient package".
 *
 * @param		InName			(optional) the name to give the new object.
 *                             	If not specified, the object will be given a unique name in the format ClassName_##, where ## is incremented each time an instance of this class is created.
 *
 * @param		InFlags			(optional, currently broken since object flags are now 64 bits) the object flags to use when creating the object. The valid values are:
 *                              (0x0000000100000000 - Supports editor undo/redo. (RF_Transactional), 0x0000000400000000 - Can be referenced by external files. (RF_Public), 0x0000400000000000 - Cannot be saved to disk. (RF_Transient), 0x0010000000000000 - Don't load object on the game client. (RF_NotForClient), 0x0020000000000000 - Don't load object on the game server. (RF_NotForServer), 0x0040000000000000 - Don't load object in the editor. (RF_NotForEdit), 0x0008000000000000 - Keep object around for editing even if unreferenced. (RF_Standalone))
 *
 * @param		InClass			the class to create an instance of
 *
 * @param		InTemplate		the object to use for initializing the new object's property values
 */
native final operator function Object new
(
   optional object   InOuter,
   optional name     InName,
   optional int      InFlags,
   class    InClass,
   object   InTemplate
);

/**
 * Returns the name of the given reference.
 *
 * @param		MemberName		either a variable or function name
 */
native final function name NameOf(String MemberName)

/**
 * This returns the number of values declared for that enum. Similar to ArrayCount.
 *
 * @param		ref			The reference to the enumeration.
 */
native final function int EnumCount(ByteProperties ref);


/**
 * The ArrayCount pseudo-function can be used to get the length of a static array.
 *
 * @param		ref			The static array reference could be as simple as the name of a static array variable in the same class or function
 *                   		or a more complex expression, such as class'TeamAI'.default.OrderList.
 */
native final function int ArrayCount(StaticArrayReference ref);
