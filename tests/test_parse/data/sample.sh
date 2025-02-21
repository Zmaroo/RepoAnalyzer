#!/bin/bash

# Constants
readonly DEFAULT_AGE=18
readonly DB_FILE="users.txt"

# Function to validate age
validate_age() {
    local age=$1
    if ! [[ "$age" =~ ^[0-9]+$ ]]; then
        echo "Error: Age must be a number"
        return 1
    elif [ "$age" -lt 0 ]; then
        echo "Error: Age cannot be negative"
        return 1
    fi
    return 0
}

# Function with return value
is_adult() {
    local age=$1
    if [ "$age" -ge "$DEFAULT_AGE" ]; then
        return 0  # true in bash
    else
        return 1  # false in bash
    fi
}

# Function with output
format_user() {
    local name=$1
    local age=$2
    echo "$name ($age years old)"
}

# Function with default parameter
create_greeting() {
    local name=$1
    local prefix=${2:-"Hello"}
    echo "$prefix, $name!"
}

# Function that processes options
process_user_opts() {
    local OPTIND opt
    local name="" age=""
    
    while getopts "n:a:" opt; do
        case $opt in
            n) name="$OPTARG" ;;
            a) age="$OPTARG" ;;
            *) return 1 ;;
        esac
    done
    
    if [ -z "$name" ] || [ -z "$age" ]; then
        echo "Error: Both name (-n) and age (-a) are required"
        return 1
    fi
    
    format_user "$name" "$age"
}

# Function using arrays
process_users() {
    local -n users=$1  # nameref to array
    local count=0
    
    for user in "${users[@]}"; do
        echo "Processing: $user"
        ((count++))
    done
    
    echo "Processed $count users"
}

# Function writing to file
save_user() {
    local name=$1
    local age=$2
    
    if ! validate_age "$age"; then
        return 1
    fi
    
    echo "$name:$age" >> "$DB_FILE"
    echo "User saved successfully"
}

# Function reading from file
get_users() {
    if [ ! -f "$DB_FILE" ]; then
        echo "No users found"
        return 1
    fi
    
    while IFS=: read -r name age; do
        format_user "$name" "$age"
    done < "$DB_FILE"
}

# Function using command substitution
get_adult_users() {
    while IFS=: read -r name age; do
        if is_adult "$age"; then
            format_user "$name" "$age"
        fi
    done < "$DB_FILE"
}

# Function demonstrating error handling
create_user() {
    local name=$1
    local age=$2
    
    if [ -z "$name" ]; then
        echo "Error: Name is required" >&2
        return 1
    fi
    
    if ! validate_age "$age"; then
        return 1
    fi
    
    save_user "$name" "$age"
}

# Function using regex
validate_name() {
    local name=$1
    if [[ "$name" =~ ^[A-Za-z][A-Za-z\ \']*$ ]]; then
        return 0
    else
        echo "Error: Invalid name format"
        return 1
    fi
}

# Function demonstrating cleanup
cleanup() {
    echo "Cleaning up..."
    [ -f "$DB_FILE" ] && rm "$DB_FILE"
    echo "Cleanup complete"
}

# Trap for cleanup
trap cleanup EXIT

# Main execution
main() {
    # Test basic functions
    echo "Creating users..."
    create_user "John" "25"
    create_user "Alice" "17"
    
    echo -e "\nAll users:"
    get_users
    
    echo -e "\nAdult users:"
    get_adult_users
    
    # Test array processing
    local -a user_list=("John (25)" "Alice (17)" "Bob (30)")
    echo -e "\nProcessing user list:"
    process_users user_list
    
    # Test option processing
    echo -e "\nProcessing user with options:"
    process_user_opts -n "Charlie" -a "22"
    
    # Test greetings
    echo -e "\nGreetings:"
    create_greeting "David"
    create_greeting "Eve" "Hi"
    
    # Test validation
    echo -e "\nValidation tests:"
    validate_name "John Doe" && echo "Valid name"
    validate_name "John123" || echo "Invalid name"
    
    validate_age "25" && echo "Valid age"
    validate_age "-5" || echo "Invalid age"
}

# Run main if script is not sourced
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main
fi 