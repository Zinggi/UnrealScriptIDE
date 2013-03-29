/**
 * Class
 * _____
 * In Unreal, classes are objects just like actors, textures, and sounds are objects. Class objects belong to the class named "class".
 * Now, there will often be cases where you'll want to store a reference to a class object, so that you can spawn an actor belonging to that class
 * (without knowing what the class is at compile-time). For example:
 * 		var() class C;
 * 		var actor A;
 * 		A = Spawn( C ); // Spawn an actor belonging to some arbitrary class C.
 * 		
 * When declaring variables that reference class objects,
 * you can optionally use the syntax class<metaclass> to limit the classes that can be referenced by the variable to classes of type metaclass (and its child classes).
 * For example, in the declaration:
 * 		var class<Actor> ActorClass;
 * The variable ActorClass may only reference a class that extends the "actor" class.
 * This is useful for improving compile-time type checking. For example, the Spawn function takes a class as a parameter,
 * but only makes sense when the given class is a subclass of Actor, and the class<classlimitor> syntax causes the compiler to enforce that requirement.
 * 
 * As with dynamic object casting, you can dynamically cast classes like this:
 * 		// casts the result of SomeFunctionCall() a class of type Actor (or subclasses of Actor)
 * 		class( SomeFunctionCall() )
 */
class Class
	native;

/**
 * Access a static function from this class instance.
 */
var const native Specifier 	Static;

/**
 * Access a default variable from this class instance.
 */
var const native Specifier 	Default;

/**
 * Access a constant from this class instance.
 */
var const native Specifier 	Const;

/**
 * Access a object from this class instance.
 */
var const native Object 	Self;

/**
 * Access a function from this class parent's instance.
 */
var const native Specifier 	Super;