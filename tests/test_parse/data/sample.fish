# Basic function
function greet
    echo "Hello, World!"
end

# Function with arguments
function greet_user -a name -d "Greet a user by name"
    echo "Hello, $name!"
end

# Function with switches
function process_file -a filename -s force -d "Process a file"
    if test -f $filename
        echo "Processing $filename..."
        if set -q _flag_force
            echo "Force mode enabled"
        end
    else
        echo "File not found: $filename"
        return 1
    end
end

# Function with variable arguments
function sum
    set total 0
    for num in $argv
        set total (math $total + $num)
    end
    echo $total
end

# Function with conditional logic
function is_valid_user -a username
    if test -z "$username"
        return 1
    end
    
    if grep -q "^$username:" /etc/passwd
        return 0
    else
        return 1
    end
end 