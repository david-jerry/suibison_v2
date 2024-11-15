from datetime import date, datetime, timedelta
from typing import Annotated, List, Optional
import uuid

from fastapi import APIRouter, BackgroundTasks, Body, Depends, File, Path, Query, Request, UploadFile, status
from fastapi.responses import JSONResponse
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlmodel import paginate

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.apps.accounts.dependencies import AccessTokenBearer, RefreshTokenBearer, TokenBearer, admin_permission_check, get_current_user
from src.apps.accounts.models import MatrixPool, MatrixPoolUsers, TokenMeter, User
from src.apps.accounts.schemas import AccessToken, ActivitiesRead, AllStatisticsRead, DeleteMessage, Message, MatrixPoolRead, MatrixUserCreateUpdate, RegAndLoginResponse, StakingCreate, TokenMeterCreate, TokenMeterRead, TokenMeterUpdate, UserCreateOrLoginSchema, UserLevelReferral, UserRead, UserUpdateSchema, UserWithReferralsRead, WithdrawEarning
from src.apps.accounts.services import AdminServices, UserServices
from src.db.engine import get_session
from src.config.settings import Config
from src.db.redis import add_jti_to_blocklist, get_level_referrers
from src.errors import ActivePoolNotFound, InvalidTelegramAuthData, InvalidToken, UserAlreadyExists
from src.utils.hashing import createAccessToken , verifyTelegramAuthData

session = Annotated[AsyncSession, Depends(get_session)]
auth_router = APIRouter()
user_router = APIRouter()
stake_router = APIRouter()
matrix_router = APIRouter()

admin_service = AdminServices()
user_service = UserServices()

@auth_router.post(
    "/start",
    status_code=status.HTTP_201_CREATED,
    response_model=RegAndLoginResponse,
    description="Initialize a new webapp instance for a user passing a `telegram_init_data` for authorization check and an `*optional* referrerId`(telegram userId) to create the level authorization. Within this endpoint is the function tto auto generate a unique wallet address and an initial activity record for the new user if it is their first time initializing the webapp else it automatically generates an accesstoken and refreshToken when the user is a returning user."
)
async def start(form_data: Annotated[UserCreateOrLoginSchema, Body()], session: session, referrer: Optional[str] = None):
    accessToken, refershToken, user = await user_service.register_new_user(False, referrer, form_data, session)
    referralsLv1List = await get_level_referrers(user.userId, 1)
    referralsLv2List = await get_level_referrers(user.userId, 2)
    referralsLv3List = await get_level_referrers(user.userId, 3)
    referralsLv4List = await get_level_referrers(user.userId, 4)
    referralsLv5List = await get_level_referrers(user.userId, 5)
    
    referralsLv1 = [UserLevelReferral(userId=user.userId, level=1, referralName=ref["name"], referralId=ref["referralId"], totalStake=ref["balance"]) for ref in referralsLv1List] if len(referralsLv1List) > 0 else []
    referralsLv2 = [UserLevelReferral(userId=user.userId, level=1, referralName=ref["name"], referralId=ref["referralId"], totalStake=ref["balance"]) for ref in referralsLv2List] if len(referralsLv2List) > 0 else []
    referralsLv3 = [UserLevelReferral(userId=user.userId, level=1, referralName=ref["name"], referralId=ref["referralId"], totalStake=ref["balance"]) for ref in referralsLv3List] if len(referralsLv3List) > 0 else []
    referralsLv4 = [UserLevelReferral(userId=user.userId, level=1, referralName=ref["name"], referralId=ref["referralId"], totalStake=ref["balance"]) for ref in referralsLv4List] if len(referralsLv4List) > 0 else []
    referralsLv5 = [UserLevelReferral(userId=user.userId, level=1, referralName=ref["name"], referralId=ref["referralId"], totalStake=ref["balance"]) for ref in referralsLv5List] if len(referralsLv5List) > 0 else []

    userResp = {
        "user": user,
        "referralsLv1": referralsLv1,
        "referralsLv2": referralsLv2,
        "referralsLv3": referralsLv3,
        "referralsLv4": referralsLv4,
        "referralsLv5": referralsLv5
    }
    return {
        "message": "Authorization Successful", 
        "accessToken": accessToken, 
        "refreshToken": refershToken, 
        "user": userResp
    }

@auth_router.get(
    "/refresh-token",
    status_code=status.HTTP_200_OK,
    response_model=AccessToken,
    description="Returns a specific user by providing their userId"
)
async def refresh_access_token(token: Annotated[User, Depends(RefreshTokenBearer())], session: session):
    expiry_timestamp = token["exp"]
    userId = token["user"]["userId"]
    
    if datetime.fromtimestamp(expiry_timestamp).date() < datetime.now().date():
        raise InvalidToken()
    
    res_user = await user_service.return_user_by_userId(userId, session)
    new_access_token = createAccessToken(user_data=token["user"])
    return {
        "message": "AccessToken generated successfully",
        "access_token": new_access_token,
        "user": res_user
    }

@auth_router.get(
    "/get-users",
    status_code=status.HTTP_200_OK,
    response_model=Page[UserRead],
    dependencies=[Depends(admin_permission_check)],
    description="This is an admin only endpoint that returns a paginated list of user datas"
)
async def get_users(session: session, date: Optional[date] = None):
    users = await admin_service.getAllUsers(date, session)
    return users

@auth_router.get(
    "/get-transactions",
    status_code=status.HTTP_200_OK,
    response_model=Page[ActivitiesRead],
    dependencies=[Depends(admin_permission_check)],
    description="Returns a paginated list of filtered actvities to an admin"
)
async def get_transactions(session: session, date: Optional[date] = None):
    transactions = await admin_service.getAllTransactions(date, session)
    return transactions

@auth_router.get(
    "/get-activities",
    status_code=status.HTTP_200_OK,
    response_model=Page[ActivitiesRead],
    dependencies=[Depends(admin_permission_check)],
    description="Returns a paginated list of all actvities to an admin"
)
async def get_activities(session: session, date: Optional[date] = None):
    activities = await admin_service.getAllActivities(date, session)
    return activities

@auth_router.patch(
    "/ban-user/{userId}",
    status_code=status.HTTP_200_OK,
    response_model=DeleteMessage,
    dependencies=[Depends(admin_permission_check)],
    description="Ban a specific user"
)
async def ban_a_user(userId: str, session: session):
    isBanned = await admin_service.banUser(userId, session)
    return {
        "message": f"{userId} has been {'banned' if isBanned else 'unbanned'}",
    }

@auth_router.post(
    "/create-token-meter",
    status_code=status.HTTP_201_CREATED,
    response_model=TokenMeterRead,
    dependencies=[Depends(admin_permission_check)],
    description="Create the token meter total capital, add an admin wallet address to transfer sui from individual user generated wallets into to show the meter bar."
)
async def create_token_meter(form_data: Annotated[TokenMeterCreate, Body()], session: session):
    tokenMeter = await admin_service.createTokenRecord(form_data, session)
    return tokenMeter

@auth_router.post(
    "/add-new-matrix-pool-user",
    status_code=status.HTTP_201_CREATED,
    response_model=DeleteMessage,
    dependencies=[Depends(admin_permission_check)],
    description="Adds a new user into the matrix pool user list for shares in the global matrix pool information."
)
async def add_new_pool_user(form_data: Annotated[MatrixUserCreateUpdate, Body()], session: session):
    matrix_user = await admin_service.addNewPoolUser(form_data, session)
    return {
            "message": f"Successfully added {matrix_user.userId} to matrix pool users"
        }

@auth_router.patch(
    "/update-token-meter",
    status_code=status.HTTP_200_OK,
    response_model=TokenMeterRead,
    dependencies=[Depends(admin_permission_check)],
    description="update the token meter."
)
async def update_token_meter(form_data: Annotated[TokenMeterUpdate, Body()], session: session):
    tokenMeter = await admin_service.updateTokenRecord(form_data, session)
    return tokenMeter

@auth_router.get(
    "/{userId}",
    status_code=status.HTTP_200_OK,
    response_model=UserWithReferralsRead,
    dependencies=[Depends(admin_permission_check)],
    description="Returns a specific user to an admin"
)
async def get_a_user(userId: str, session: session):
    user = session.exec(select(User).where(User.userId == userId)).first()
    referralsLv1List = await get_level_referrers(user.userId, 1)
    referralsLv2List = await get_level_referrers(user.userId, 2)
    referralsLv3List = await get_level_referrers(user.userId, 3)
    referralsLv4List = await get_level_referrers(user.userId, 4)
    referralsLv5List = await get_level_referrers(user.userId, 5)
    
    referralsLv1 = [UserLevelReferral(userId=user.userId, level=1, referralName=ref["name"], referralId=ref["referralId"], totalStake=ref["balance"]) for ref in referralsLv1List] if len(referralsLv1List) > 0 else []
    referralsLv2 = [UserLevelReferral(userId=user.userId, level=1, referralName=ref["name"], referralId=ref["referralId"], totalStake=ref["balance"]) for ref in referralsLv2List] if len(referralsLv2List) > 0 else []
    referralsLv3 = [UserLevelReferral(userId=user.userId, level=1, referralName=ref["name"], referralId=ref["referralId"], totalStake=ref["balance"]) for ref in referralsLv3List] if len(referralsLv3List) > 0 else []
    referralsLv4 = [UserLevelReferral(userId=user.userId, level=1, referralName=ref["name"], referralId=ref["referralId"], totalStake=ref["balance"]) for ref in referralsLv4List] if len(referralsLv4List) > 0 else []
    referralsLv5 = [UserLevelReferral(userId=user.userId, level=1, referralName=ref["name"], referralId=ref["referralId"], totalStake=ref["balance"]) for ref in referralsLv5List] if len(referralsLv5List) > 0 else []

    return {
        "user": user, 
        "referralsLv1": referralsLv1,
        "referralsLv2": referralsLv2,
        "referralsLv3": referralsLv3,
        "referralsLv4": referralsLv4,
        "referralsLv5": referralsLv5,
    }






# User Endpoints
@user_router.get(
    "/token-meter",
    status_code=status.HTTP_200_OK,
    response_model=Optional[TokenMeterRead],
    description="Get token meter."
)
async def get_token_meter(session: session):
    db_result = await session.exec(select(TokenMeter))
    return db_result.first()

@user_router.get(
    "/me",
    status_code=status.HTTP_200_OK,
    response_model=UserWithReferralsRead,
    dependencies=[Depends(get_current_user)],
    description="Returns a paginated list of all actvities to an admin"
)
async def me(user: Annotated[User, Depends(get_current_user)]):
    referralsLv1List = await get_level_referrers(user.userId, 1)
    referralsLv2List = await get_level_referrers(user.userId, 2)
    referralsLv3List = await get_level_referrers(user.userId, 3)
    referralsLv4List = await get_level_referrers(user.userId, 4)
    referralsLv5List = await get_level_referrers(user.userId, 5)
    
    referralsLv1 = [UserLevelReferral(userId=user.userId, level=1, referralName=ref["name"], referralId=ref["referralId"], totalStake=ref["balance"]) for ref in referralsLv1List] if len(referralsLv1List) > 0 else []
    referralsLv2 = [UserLevelReferral(userId=user.userId, level=1, referralName=ref["name"], referralId=ref["referralId"], totalStake=ref["balance"]) for ref in referralsLv2List] if len(referralsLv2List) > 0 else []
    referralsLv3 = [UserLevelReferral(userId=user.userId, level=1, referralName=ref["name"], referralId=ref["referralId"], totalStake=ref["balance"]) for ref in referralsLv3List] if len(referralsLv3List) > 0 else []
    referralsLv4 = [UserLevelReferral(userId=user.userId, level=1, referralName=ref["name"], referralId=ref["referralId"], totalStake=ref["balance"]) for ref in referralsLv4List] if len(referralsLv4List) > 0 else []
    referralsLv5 = [UserLevelReferral(userId=user.userId, level=1, referralName=ref["name"], referralId=ref["referralId"], totalStake=ref["balance"]) for ref in referralsLv5List] if len(referralsLv5List) > 0 else []
    
    return {
        "user": user, 
        "referralsLv1": referralsLv1,
        "referralsLv2": referralsLv2,
        "referralsLv3": referralsLv3,
        "referralsLv4": referralsLv4,
        "referralsLv5": referralsLv5,
    }

@user_router.get(
    "/me/activities",
    status_code=status.HTTP_200_OK,
    response_model=Page[ActivitiesRead],
    dependencies=[Depends(get_current_user)],
    description="Returns a paginated list of all actvities to an admin"
)
async def get_my_activities(user: Annotated[User, Depends(get_current_user)], session: session):
    activities = await user_service.getUserActivities(user, session)
    return activities

@user_router.patch(
    "/me",
    status_code=status.HTTP_200_OK,
    response_model=UserWithReferralsRead,
    dependencies=[Depends(get_current_user)],
    description="Update records for a specific user by providing their userId as a required field ad then the body form data to update with"
)
async def update_profile(user: Annotated[User, Depends(get_current_user)], form_data: Annotated[UserUpdateSchema, Body()], session: session):
    res_user = await user_service.updateUserProfile(user, form_data, session)
    referralsLv1List = await get_level_referrers(res_user.userId, 1)
    referralsLv2List = await get_level_referrers(res_user.userId, 2)
    referralsLv3List = await get_level_referrers(res_user.userId, 3)
    referralsLv4List = await get_level_referrers(res_user.userId, 4)
    referralsLv5List = await get_level_referrers(res_user.userId, 5)
    
    referralsLv1 = [UserLevelReferral(userId=res_user.userId, level=1, referralName=ref["name"], referralId=ref["referralId"], totalStake=ref["balance"]) for ref in referralsLv1List] if len(referralsLv1List) > 0 else []
    referralsLv2 = [UserLevelReferral(userId=res_user.userId, level=1, referralName=ref["name"], referralId=ref["referralId"], totalStake=ref["balance"]) for ref in referralsLv2List] if len(referralsLv2List) > 0 else []
    referralsLv3 = [UserLevelReferral(userId=res_user.userId, level=1, referralName=ref["name"], referralId=ref["referralId"], totalStake=ref["balance"]) for ref in referralsLv3List] if len(referralsLv3List) > 0 else []
    referralsLv4 = [UserLevelReferral(userId=res_user.userId, level=1, referralName=ref["name"], referralId=ref["referralId"], totalStake=ref["balance"]) for ref in referralsLv4List] if len(referralsLv4List) > 0 else []
    referralsLv5 = [UserLevelReferral(userId=res_user.userId, level=1, referralName=ref["name"], referralId=ref["referralId"], totalStake=ref["balance"]) for ref in referralsLv5List] if len(referralsLv5List) > 0 else []
    
    return {
        "user": res_user, 
        "referralsLv1": referralsLv1,
        "referralsLv2": referralsLv2,
        "referralsLv3": referralsLv3,
        "referralsLv4": referralsLv4,
        "referralsLv5": referralsLv5,
    }

