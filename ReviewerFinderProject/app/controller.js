'use strict';
angular.module('app')
.controller('controller', function($http, $scope, service){
	$scope.error = "";
	$scope.isErr_login = false;
	$scope.isLogin = true;
	$scope.isMain = false;
	$scope.user = {};
	$scope.userAuth = "";

	$scope.hideError = function(){
		$scope.isErr_login = false;
	}
	$scope.queryShow = function(){
		$scope.isLogin = false;
		$scope.isMain = true;
	}
	$scope.loginShow = function(){
		$scope.user = {};
		service.clearCredential;
		$scope.isLogin = true;
		$scope.isMain = false;
	}

	$scope.login = function(){
		console.log($scope.user.username + " " + $scope.user.password);
		service.login($scope.user, function(data){
			console.log(data.status);
			if(data.status == '200'){
				console.log("You have logged in successfully");
				$scope.queryShow();
			}else{
				$scope.isErr_login = true;
			}
		}, function(err){
			$scope.isErr_login = true;
		});
	}
  $scope.submit = function(){
			$scope.isData = false;
			$scope.isProgress = false;
			$scope.error = "";
            if($scope.query == undefined){
                $scope.error = "Pease provide query.";
            }else{
								$scope.isProgress = true;
                service.getReviewrs($scope.query, function(data){
									$scope.isProgress = false;
                  console.log(angular.toJson(data));
                  $scope.output = data;
									$scope.isData = true;
									if($scope.output['processTime']){
											console.log("process time");
									}
									if($scope.output['Error']){
										console.log("Error output");
										$scope.error = $scope.output['Error'];
									}
									if($scope.output['Info']){
										console.log("Info output");
										$scope.error = 'Info: ' + $scope.output['Info'];
									}
            },function(erro){
							$scope.isProgress = false;
                    $scope.error = "Error: Connection Error";
                  }
                );
            }
        }
});
