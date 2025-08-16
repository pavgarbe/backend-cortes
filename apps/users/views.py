from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.response import Response
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth.hashers import make_password
from .models import User
from datetime import timedelta


############## LOGIN ##############################################

APP_TOKEN_EXPIRATION = timedelta(days=10000)

class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)

        data["id"] = self.user.id
        data["rol"] = self.user.rol
        data["nombres"] = self.user.nombres
        data["apellidos"] = self.user.apellidos
        data["email"] = self.user.email

        return data

class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer

############## API USUARIOS ##############################################

class UserCreate(APIView):

    def post(self, request, format=None):
        data = request.data
        user = User.objects.filter(email=data['email']).first()
        if user:
            return Response({'message': 'El usuario ya existe'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            user = User.objects.create_user(
                nombres = data['nombres'],
                apellidos = data['apellidos'],
                rol = data['rol'],
                password = data['password'],
                email=data['email']
            )
        return Response({'Usuario creado'}, status=status.HTTP_201_CREATED)


class UserList(APIView):
    def get(self, request, format=None):
        users = User.objects.all()
        list = []
        for user in users:
            list.append({
                'id': user.id,
                'nombres': user.nombres,
                'apellidos': user.apellidos,
                'rol': user.rol,
                'email': user.email,
            })
        return Response(list, status=status.HTTP_200_OK)

class UserDelete(APIView):

    def delete(self, request, id, format=None):
        user = User.objects.filter(id=id).first()
        if user:
            user.delete()
            return Response({'message': 'Usuario eliminado correctamente'}, status=status.HTTP_200_OK)
        else:
            return Response({'message': 'El usuario no existe'}, status=status.HTTP_400_BAD_REQUEST)


class GetUser(APIView):

    def post(self, request, format=None):
        user = User.objects.get(email=request.GET.get('email'))
        if user:
            user = {
                'id': user.id,
                'email': user.email,
                'nombres': user.nombres,
                'apellidos': user.apellidos,
                'rol': user.rol
            }

            return Response(user, status=status.HTTP_200_OK)
        else:
            return Response({'message': 'El usuario no existe'}, status=status.HTTP_400_BAD_REQUEST)


class UserUpdate(APIView):
    
        def put(self, request, id, format=None):
            data = request.data
            user = User.objects.filter(id=id).first()

            if user:
                if data['nombres'] != '':
                    user.nombres = data['nombres']
                if data['apellidos'] != '':
                    user.apellidos = data['apellidos']
                if data['rol'] != '':
                    user.rol = data['rol']
                if data['email'] != '':
                    user.email = data['email']
                if data['password'] != '':
                    hash = make_password(data['password'])
                    user.password = hash
                user.save()
                
                return Response({'message':'El usuario ha sido actualizado'}, status=status.HTTP_200_OK)
            else:
                return Response({'message': 'El usuario no existe'}, status=status.HTTP_400_BAD_REQUEST)