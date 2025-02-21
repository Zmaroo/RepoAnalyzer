#!/usr/bin/env tclsh

# Create a namespace for user management
namespace eval UserManager {
    # Variable to store users
    variable users [dict create]
    
    # Constants
    variable DEFAULT_AGE 18
    
    # Constructor-like procedure
    proc create_user {name age} {
        if {$age < 0} {
            error "Age cannot be negative"
        }
        return [dict create name $name age $age]
    }
    
    # Procedure with optional arguments
    proc format_user {user {verbose 0}} {
        set name [dict get $user name]
        set age [dict get $user age]
        if {$verbose} {
            return "$name is $age years old"
        } else {
            return "$name ($age)"
        }
    }
    
    # Procedure with variable arguments
    proc process_users {args} {
        set results [list]
        foreach user $args {
            lappend results [format_user $user]
        }
        return $results
    }
    
    # Procedure with return value
    proc is_adult {user} {
        variable DEFAULT_AGE
        set age [dict get $user age]
        return [expr {$age >= $DEFAULT_AGE}]
    }
    
    # Procedure using upvar (reference parameters)
    proc update_user {user_var name age} {
        upvar 1 $user_var user
        dict set user name $name
        dict set user age $age
    }
    
    # Procedure with error handling
    proc validate_user {user} {
        if {![dict exists $user name] || ![dict exists $user age]} {
            error "Invalid user structure"
        }
        set age [dict get $user age]
        if {![string is integer $age]} {
            error "Age must be an integer"
        }
        if {$age < 0} {
            error "Age cannot be negative"
        }
        return 1
    }
    
    # Procedure using regular expressions
    proc validate_name {name} {
        return [regexp {^[A-Za-z][A-Za-z\ \']*$} $name]
    }
    
    # Procedure with namespace variables
    proc add_user {user} {
        variable users
        set name [dict get $user name]
        dict set users $name $user
    }
    
    # Procedure returning multiple values
    proc get_user_stats {user_list} {
        set total [llength $user_list]
        set adult_count 0
        foreach user $user_list {
            if {[is_adult $user]} {
                incr adult_count
            }
        }
        return [list $total $adult_count]
    }
    
    # Procedure using list operations
    proc find_user {user_list name} {
        foreach user $user_list {
            if {[dict get $user name] eq $name} {
                return $user
            }
        }
        return ""
    }
    
    # Procedure with default values
    proc create_greeting {{prefix "Hello"} name} {
        return "$prefix, $name!"
    }
    
    # Procedure using string manipulation
    proc process_name {name} {
        set name [string trim $name]
        set name [string totitle [string tolower $name]]
        return $name
    }
    
    # Procedure using file operations
    proc save_users {filename user_list} {
        set f [open $filename w]
        foreach user $user_list {
            puts $f [list [dict get $user name] [dict get $user age]]
        }
        close $f
    }
    
    # Procedure using file reading
    proc load_users {filename} {
        set users [list]
        set f [open $filename r]
        while {[gets $f line] >= 0} {
            lassign $line name age
            lappend users [create_user $name $age]
        }
        close $f
        return $users
    }
}

# Main execution
proc main {} {
    # Create test users
    set user1 [UserManager::create_user "John" 25]
    set user2 [UserManager::create_user "Alice" 17]
    set users [list $user1 $user2]
    
    # Test basic functions
    puts "Users:"
    foreach user $users {
        puts [UserManager::format_user $user]
    }
    
    # Test verbose formatting
    puts "\nVerbose format:"
    foreach user $users {
        puts [UserManager::format_user $user 1]
    }
    
    # Test adult checking
    puts "\nAdult check:"
    foreach user $users {
        set name [dict get $user name]
        if {[UserManager::is_adult $user]} {
            puts "$name is an adult"
        } else {
            puts "$name is not an adult"
        }
    }
    
    # Test user updating
    puts "\nUpdating user:"
    set test_user $user1
    UserManager::update_user test_user "John Doe" 26
    puts [UserManager::format_user $test_user]
    
    # Test validation
    puts "\nValidation:"
    foreach user $users {
        if {[catch {UserManager::validate_user $user} result]} {
            puts "Validation failed: $result"
        } else {
            puts "User is valid"
        }
    }
    
    # Test name validation
    puts "\nName validation:"
    puts "John Doe: [UserManager::validate_name "John Doe"]"
    puts "John123: [UserManager::validate_name "John123"]"
    
    # Test user stats
    puts "\nUser statistics:"
    lassign [UserManager::get_user_stats $users] total adult_count
    puts "Total users: $total"
    puts "Adult users: $adult_count"
    
    # Test user finding
    puts "\nFinding user:"
    set found_user [UserManager::find_user $users "John"]
    if {$found_user ne ""} {
        puts "Found: [UserManager::format_user $found_user]"
    }
    
    # Test name processing
    puts "\nProcessed names:"
    foreach user $users {
        set name [dict get $user name]
        puts [UserManager::process_name $name]
    }
    
    # Test file operations
    puts "\nTesting file operations:"
    UserManager::save_users "test_users.txt" $users
    set loaded_users [UserManager::load_users "test_users.txt"]
    puts "Loaded users:"
    foreach user $loaded_users {
        puts [UserManager::format_user $user]
    }
    file delete "test_users.txt"
}

# Run main if script is being run directly
if {[info script] eq $argv0} {
    main
} 