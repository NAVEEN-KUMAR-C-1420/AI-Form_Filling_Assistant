# Test profile data endpoint end-to-end

$baseUrl = "http://localhost:8000"
$email = "naveen@gmail.com"
$password = "Naveen@123"

Write-Host "1. Attempting login..." -ForegroundColor Yellow
try {
    $loginBody = @{email=$email; password=$password} | ConvertTo-Json
    $loginResponse = Invoke-RestMethod -Uri "$baseUrl/auth/login" -Method Post -Body $loginBody -ContentType "application/json" -ErrorAction Stop
    
    $token = $loginResponse.access_token
    Write-Host "Login successful!" -ForegroundColor Green
    Write-Host "Token: $($token.Substring(0, 20))..." -ForegroundColor Gray
} catch {
    Write-Host "Login failed: $($_.Exception.Message)" -ForegroundColor Red
    $errorDetail = $_.ErrorDetails.Message | ConvertFrom-Json
    Write-Host "Detail: $($errorDetail.detail)" -ForegroundColor Red
    exit 1
}

Write-Host "`n2. Fetching profile data..." -ForegroundColor Yellow
try {
    $headers = @{Authorization="Bearer $token"}
    $profileResponse = Invoke-RestMethod -Uri "$baseUrl/user/profile-data" -Headers $headers -ErrorAction Stop
    
    Write-Host "Profile data fetched successfully!" -ForegroundColor Green
    
    Write-Host "`n3. Profile Data Summary:" -ForegroundColor Cyan
    Write-Host "User ID: $($profileResponse.user_id)" -ForegroundColor White
    Write-Host "Documents: $($profileResponse.documents.Count)" -ForegroundColor White
    Write-Host "Entities: $($profileResponse.entities.PSObject.Properties.Count)" -ForegroundColor White
    Write-Host "Entity Details: $($profileResponse.entity_details.Count)" -ForegroundColor White
    
    if ($profileResponse.entities.PSObject.Properties.Count -gt 0) {
        Write-Host "`n4. Entities List:" -ForegroundColor Cyan
        foreach ($prop in $profileResponse.entities.PSObject.Properties) {
            $entity = $prop.Value
            Write-Host "  - $($prop.Name): $($entity.value)" -ForegroundColor White
        }
    }
    
    if ($profileResponse.entity_details.Count -gt 0) {
        Write-Host "`n5. First 3 Entity Details:" -ForegroundColor Cyan
        $profileResponse.entity_details | Select-Object -First 3 | ForEach-Object {
            Write-Host "  ID: $($_.id)" -ForegroundColor Gray
            Write-Host "  Type: $($_.entity_type)" -ForegroundColor White
            Write-Host "  Value: $($_.value)" -ForegroundColor White
            Write-Host "  Is Sensitive: $($_.is_sensitive)" -ForegroundColor Gray
            Write-Host ""
        }
    }
    
    Write-Host "`nAll tests passed!" -ForegroundColor Green
    
} catch {
    Write-Host "Profile fetch failed: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.ErrorDetails) {
        Write-Host "Error details: $($_.ErrorDetails.Message)" -ForegroundColor Red
    }
    exit 1
}
