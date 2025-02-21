cmake_minimum_required(VERSION 3.10)
project(SampleProject)

# Variables
set(SOURCE_FILES main.cpp user.cpp)
set(CMAKE_CXX_STANDARD 17)

# Function definition
function(add_prefix prefix output_list)
    set(temp_list "")
    foreach(item ${ARGN})
        list(APPEND temp_list "${prefix}${item}")
    endforeach()
    set(${output_list} ${temp_list} PARENT_SCOPE)
endfunction()

# Add executable
add_executable(${PROJECT_NAME} ${SOURCE_FILES})

# Add library
add_library(user_lib STATIC ${SOURCE_FILES})

# Target properties
set_target_properties(${PROJECT_NAME} PROPERTIES
    CXX_STANDARD 17
    CXX_STANDARD_REQUIRED ON
) 