# Sample PowerShell functions

# Basic function
function Get-User {
    param(
        [string]$Name,
        [int]$Age = 0
    )
    return @{
        Name = $Name
        Age = $Age
    }
}

# Advanced function with attributes
[CmdletBinding()]
param()
function New-User {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)]
        [string]$Name,
        
        [Parameter()]
        [ValidateRange(0, 150)]
        [int]$Age = 0,
        
        [Parameter()]
        [string]$Email
    )
    
    process {
        $user = @{
            Name = $Name
            Age = $Age
            Email = $Email
        }
        return $user
    }
}

# Function with script block
$ProcessUser = {
    param($User)
    
    if ($User.Age -lt 0) {
        throw "Invalid age"
    }
    if ($User.Age -lt 18) {
        Write-Warning "User is underage"
    }
    
    return $User
}

# Filter function
filter Format-User {
    @{
        DisplayName = $_.Name.ToUpper()
        IsAdult = $_.Age -ge 18
    }
}

# Function with dynamic parameters
function Get-DynamicUser {
    [CmdletBinding()]
    param()
    
    dynamicparam {
        $paramDictionary = New-Object System.Management.Automation.RuntimeDefinedParameterDictionary
        
        $attributeCollection = New-Object System.Collections.ObjectModel.Collection[System.Attribute]
        $paramAttribute = New-Object System.Management.Automation.ParameterAttribute
        $paramAttribute.Mandatory = $true
        $attributeCollection.Add($paramAttribute)
        
        $dynParam = New-Object System.Management.Automation.RuntimeDefinedParameter(
            'UserType', [string], $attributeCollection
        )
        
        $paramDictionary.Add('UserType', $dynParam)
        return $paramDictionary
    }
    
    process {
        $UserType = $PSBoundParameters['UserType']
        return "Processing $UserType user"
    }
}

function Get-UserInfo {
    param(
        [string]$Name,
        [int]$Age
    )
    
    return @{
        Name = $Name
        Age = $Age
        IsAdult = ($Age -ge 18)
    }
}

$user = Get-UserInfo -Name "John" -Age 25
Write-Output $user 